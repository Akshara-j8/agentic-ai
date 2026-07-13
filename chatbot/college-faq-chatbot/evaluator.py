"""
RAGAS evaluation module for the College FAQ Chatbot.

Workflow:
  1. Load existing ChromaDB vector store.
  2. Optionally auto-generate test cases from knowledge base chunks.
  3. Run the RAG pipeline on each test question.
  4. Evaluate with RAGAS metrics:
       - Faithfulness
       - Answer Relevancy
       - Context Precision
       - Context Recall
  5. Save a full evaluation report to evaluation/report.json.

Run directly:
    python evaluator.py
"""
import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_DIR,
    DEFAULT_TEST_COUNT,
    EVALUATION_DIR,
    EVALUATION_REPORT_FILE,
    OPENAI_API_KEY,
    RAGAS_EMBEDDING_MODEL,
    RAGAS_LLM_MODEL,
    TEST_CASES_DIR,
)
from ingest import get_embeddings
from prompts import TEST_CASE_GENERATION_PROMPT
from rag import build_chat_history, get_llm, query
from utils import setup_logger

logger = setup_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Test case generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_test_cases(
    n_total: int = DEFAULT_TEST_COUNT,
    save_path: Optional[Path] = None,
) -> List[Dict[str, str]]:
    """Automatically generate question-answer test cases from the knowledge base.

    Samples random chunks from ChromaDB, sends them to the LLM with a
    generation prompt, and collects (question, ground_truth) pairs.

    Args:
        n_total:   Approximate total number of test cases to generate.
        save_path: If provided, saves the cases to this JSON file.

    Returns:
        List of dicts with keys "question" and "ground_truth".
    """
    from langchain_chroma import Chroma
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import PromptTemplate

    if not CHROMA_DB_DIR.exists() or not any(CHROMA_DB_DIR.iterdir()):
        raise RuntimeError(
            "Vector store not found. Run `python ingest.py` first."
        )

    logger.info("Generating %d test cases …", n_total)

    # Load vector store and get random chunks
    embeddings = get_embeddings()
    store = Chroma(
        persist_directory=str(CHROMA_DB_DIR),
        embedding_function=embeddings,
        collection_name=CHROMA_COLLECTION_NAME,
    )
    total_chunks = store._collection.count()
    if total_chunks == 0:
        raise RuntimeError("ChromaDB is empty. Run `python ingest.py` first.")

    # Sample a subset of chunks for generation
    all_docs = store.get()  # returns dict with 'documents', 'metadatas'
    raw_texts: List[str] = all_docs.get("documents", [])
    if not raw_texts:
        raise RuntimeError("No documents found in ChromaDB.")

    sample_size = min(n_total, len(raw_texts))
    sampled_texts = random.sample(raw_texts, sample_size)

    llm = get_llm(streaming=False)
    prompt_template = PromptTemplate.from_template(TEST_CASE_GENERATION_PROMPT)
    chain = prompt_template | llm | StrOutputParser()

    # Generate ~2 cases per sampled chunk, stopping at n_total
    test_cases: List[Dict[str, str]] = []
    per_chunk = max(1, n_total // sample_size)

    for passage in sampled_texts:
        if len(test_cases) >= n_total:
            break
        try:
            raw_json = chain.invoke(
                {"passage": passage[:1500], "n": per_chunk}
            )
            # Strip markdown fences if present
            raw_json = raw_json.strip()
            if raw_json.startswith("```"):
                raw_json = raw_json.split("```")[1]
                if raw_json.startswith("json"):
                    raw_json = raw_json[4:]
            pairs: List[Dict[str, str]] = json.loads(raw_json)
            for pair in pairs:
                test_cases.append(
                    {
                        "question": pair.get("question", "").strip(),
                        "ground_truth": pair.get("answer", "").strip(),
                    }
                )
                if len(test_cases) >= n_total:
                    break
        except (json.JSONDecodeError, KeyError, Exception) as exc:
            logger.warning("Skipping chunk (parse error): %s", exc)
            continue

    logger.info("Generated %d test cases.", len(test_cases))

    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(test_cases, f, indent=2, ensure_ascii=False)
        logger.info("Test cases saved to %s", save_path)

    return test_cases


def load_test_cases(path: Path) -> List[Dict[str, str]]:
    """Load test cases from a JSON file.

    Args:
        path: Path to a JSON file containing a list of
              {question, ground_truth} dicts.

    Returns:
        List of test case dicts.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Test case file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Loaded %d test cases from %s", len(data), path)
    return data


# ─────────────────────────────────────────────────────────────────────────────
#  RAG pipeline runner for evaluation
# ─────────────────────────────────────────────────────────────────────────────

def run_rag_for_evaluation(
    test_cases: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Execute the RAG pipeline on each test case.

    Args:
        test_cases: List of dicts with "question" and "ground_truth".

    Returns:
        List of dicts with RAGAS-compatible fields:
        - question
        - answer
        - contexts  (list of retrieved chunk strings)
        - ground_truth
    """
    results: List[Dict[str, Any]] = []
    total = len(test_cases)

    for i, case in enumerate(test_cases, 1):
        question = case["question"]
        ground_truth = case.get("ground_truth", "")
        logger.info("[%d/%d] Evaluating: %s", i, total, question[:80])

        try:
            rag_response = query(question=question, chat_history=[])
            contexts = [doc.page_content for doc in rag_response.source_documents]
            results.append(
                {
                    "question": question,
                    "answer": rag_response.answer,
                    "contexts": contexts,
                    "ground_truth": ground_truth,
                }
            )
        except Exception as exc:
            logger.error("RAG failed for question '%s': %s", question[:60], exc)
            results.append(
                {
                    "question": question,
                    "answer": "ERROR",
                    "contexts": [],
                    "ground_truth": ground_truth,
                }
            )

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  RAGAS scoring
# ─────────────────────────────────────────────────────────────────────────────

def run_ragas_evaluation(
    rag_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Score RAG results with RAGAS metrics.

    Metrics evaluated:
    - faithfulness       : Is the answer grounded in the retrieved context?
    - answer_relevancy   : Is the answer relevant to the question?
    - context_precision  : Are the retrieved chunks precise?
    - context_recall     : Do the chunks cover the ground truth?

    Args:
        rag_results: Output from run_rag_for_evaluation().

    Returns:
        Dict with metric names mapped to float scores (0–1).
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        from langchain_openai import ChatOpenAI as LCChatOpenAI
        from langchain_openai import OpenAIEmbeddings as LCOpenAIEmbeddings
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
    except ImportError as exc:
        raise ImportError(
            f"RAGAS or datasets package missing: {exc}\n"
            "Install with: pip install ragas datasets"
        ) from exc

    if not rag_results:
        raise ValueError("No RAG results provided for evaluation.")

    # Build HuggingFace Dataset
    dataset = Dataset.from_list(rag_results)

    # RAGAS needs OpenAI directly (not via OpenRouter)
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is required for RAGAS evaluation.\n"
            "RAGAS internally calls OpenAI for its own scoring."
        )

    ragas_llm = LangchainLLMWrapper(
        LCChatOpenAI(
            model=RAGAS_LLM_MODEL,
            openai_api_key=OPENAI_API_KEY,
            temperature=0,
        )
    )
    ragas_embeddings = LangchainEmbeddingsWrapper(
        LCOpenAIEmbeddings(
            model=RAGAS_EMBEDDING_MODEL,
            openai_api_key=OPENAI_API_KEY,
        )
    )

    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    for metric in metrics:
        metric.llm = ragas_llm
        if hasattr(metric, "embeddings"):
            metric.embeddings = ragas_embeddings

    logger.info("Running RAGAS evaluation on %d samples …", len(rag_results))
    result = evaluate(dataset=dataset, metrics=metrics)
    scores: Dict[str, float] = {}

    # result is a ragas EvaluationResult — convert to plain dict
    result_df = result.to_pandas()
    for col in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        if col in result_df.columns:
            scores[col] = round(float(result_df[col].mean()), 4)
        else:
            scores[col] = 0.0

    logger.info("RAGAS scores: %s", scores)
    return scores


# ─────────────────────────────────────────────────────────────────────────────
#  Report generation
# ─────────────────────────────────────────────────────────────────────────────

def build_report(
    scores: Dict[str, float],
    rag_results: List[Dict[str, Any]],
    test_cases: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Assemble the full evaluation report dict.

    Args:
        scores:      RAGAS metric scores.
        rag_results: Per-question RAG outputs.
        test_cases:  Original test cases.

    Returns:
        Complete report dictionary.
    """
    overall_score = round(sum(scores.values()) / len(scores), 4) if scores else 0.0
    pass_rate = round(
        sum(1 for v in scores.values() if v >= 0.7) / len(scores), 4
    ) if scores else 0.0

    # Identify weakest metric
    weakest = min(scores, key=scores.get) if scores else "N/A"

    # Per-metric recommendations
    recommendations: List[str] = []
    if scores.get("faithfulness", 1.0) < 0.7:
        recommendations.append(
            "Faithfulness is low — strengthen the system prompt to prevent "
            "hallucination, or reduce LLM temperature."
        )
    if scores.get("answer_relevancy", 1.0) < 0.7:
        recommendations.append(
            "Answer relevancy is low — improve the query-condensation prompt "
            "or increase TOP_K to retrieve more context."
        )
    if scores.get("context_precision", 1.0) < 0.7:
        recommendations.append(
            "Context precision is low — consider reducing chunk_size or "
            "adding metadata filtering."
        )
    if scores.get("context_recall", 1.0) < 0.7:
        recommendations.append(
            "Context recall is low — increase chunk_overlap or TOP_K to "
            "ensure all relevant information is retrieved."
        )
    if not recommendations:
        recommendations.append("All metrics above 0.7 — system is performing well!")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_test_cases": len(test_cases),
        "overall_score": overall_score,
        "pass_rate": pass_rate,
        "weakest_metric": weakest,
        "metrics": scores,
        "recommendations": recommendations,
        "per_question_results": rag_results,
    }


def save_report(report: Dict[str, Any], path: Optional[Path] = None) -> Path:
    """Save the evaluation report as JSON.

    Args:
        report: The report dict from build_report().
        path:   Override file path. Defaults to evaluation/report.json.

    Returns:
        Path where the report was saved.
    """
    if path is None:
        EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
        path = EVALUATION_DIR / EVALUATION_REPORT_FILE

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info("Evaluation report saved to %s", path)
    return path


def load_report(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load a saved evaluation report.

    Args:
        path: Override file path. Defaults to evaluation/report.json.

    Returns:
        Report dict, or None if not found.
    """
    if path is None:
        path = EVALUATION_DIR / EVALUATION_REPORT_FILE
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
#  Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def run_full_evaluation(
    test_cases_path: Optional[Path] = None,
    n_auto_generate: int = DEFAULT_TEST_COUNT,
) -> Dict[str, Any]:
    """End-to-end evaluation: load/generate test cases → RAG → RAGAS → report.

    Args:
        test_cases_path: If provided, load test cases from this JSON file.
                         Otherwise auto-generate from the knowledge base.
        n_auto_generate: Number of test cases to auto-generate if none provided.

    Returns:
        Full report dict (also saved to evaluation/report.json).
    """
    # 1. Obtain test cases
    if test_cases_path and test_cases_path.exists():
        test_cases = load_test_cases(test_cases_path)
    else:
        auto_path = TEST_CASES_DIR / "auto_generated.json"
        test_cases = generate_test_cases(
            n_total=n_auto_generate,
            save_path=auto_path,
        )

    if not test_cases:
        raise ValueError("No test cases available for evaluation.")

    # 2. Run RAG pipeline
    rag_results = run_rag_for_evaluation(test_cases)

    # 3. RAGAS scoring
    scores = run_ragas_evaluation(rag_results)

    # 4. Build and save report
    report = build_report(scores, rag_results, test_cases)
    save_report(report)

    return report


# ─────────────────────────────────────────────────────────────────────────────
#  CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Run RAGAS evaluation on the College FAQ Chatbot."
    )
    parser.add_argument(
        "--test-cases",
        type=Path,
        default=None,
        help="Path to a JSON file of {question, ground_truth} pairs. "
             "Omit to auto-generate.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=DEFAULT_TEST_COUNT,
        help=f"Number of test cases to auto-generate (default: {DEFAULT_TEST_COUNT}).",
    )
    args = parser.parse_args()

    try:
        report = run_full_evaluation(
            test_cases_path=args.test_cases,
            n_auto_generate=args.n,
        )
        print("\n" + "═" * 50)
        print("  RAGAS Evaluation Complete")
        print("═" * 50)
        print(f"  Overall Score  : {report['overall_score']:.2%}")
        print(f"  Pass Rate      : {report['pass_rate']:.2%}")
        print(f"  Weakest Metric : {report['weakest_metric']}")
        print("\n  Metric Scores:")
        for k, v in report["metrics"].items():
            print(f"    {k:<25}: {v:.4f}")
        print("\n  Recommendations:")
        for rec in report["recommendations"]:
            print(f"    • {rec}")
        print(f"\n  Report saved to: evaluation/{EVALUATION_REPORT_FILE}")
        print("═" * 50 + "\n")
    except Exception as e:
        logger.error("Evaluation failed: %s", e)
        sys.exit(1)
