"""
RAG chain module for the College FAQ Chatbot.

Provides:
- Retriever construction (ChromaDB + metadata filtering)
- LLM construction (GPT-4o-mini via OpenRouter)
- Conversational RAG chain with memory
- Streaming response support
- Latency + token usage tracking
"""
import logging
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

from config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_DIR,
    EMBEDDING_MODEL,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    TOP_K,
)
from prompts import CONDENSE_QUESTION_PROMPT, RAG_CHAT_PROMPT, build_rag_prompt
from utils import Timer, estimate_tokens, format_chunks_for_context

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  LLM — GPT-4o-mini via OpenRouter
# ─────────────────────────────────────────────────────────────────────────────

def get_llm(streaming: bool = False) -> ChatOpenAI:
    """Instantiate GPT-4o-mini through the OpenRouter gateway.

    Args:
        streaming: If True, enable streaming tokens.

    Returns:
        Configured ChatOpenAI instance.

    Raises:
        ValueError: If OPENROUTER_API_KEY is missing.
    """
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY is missing from .env.\n"
            "Get a free key at https://openrouter.ai/keys"
        )
    return ChatOpenAI(
        model=LLM_MODEL,
        openai_api_key=OPENROUTER_API_KEY,
        openai_api_base=OPENROUTER_BASE_URL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        streaming=streaming,
        # Pass required OpenRouter headers
        default_headers={
            "HTTP-Referer": "https://college-faq-chatbot",
            "X-Title": "BVRITH College FAQ Chatbot",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Embeddings — local HuggingFace (no API key required)
# ─────────────────────────────────────────────────────────────────────────────

def get_embeddings() -> HuggingFaceEmbeddings:
    """Return local HuggingFace embeddings (all-MiniLM-L6-v2).

    Returns:
        Configured HuggingFaceEmbeddings instance.
    """
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Vector store + retriever
# ─────────────────────────────────────────────────────────────────────────────

def get_vector_store() -> Chroma:
    """Load the persisted ChromaDB vector store.

    Returns:
        Chroma vector store instance.

    Raises:
        RuntimeError: If the vector store has not been created yet.
    """
    if not CHROMA_DB_DIR.exists() or not any(CHROMA_DB_DIR.iterdir()):
        raise RuntimeError(
            "Vector store not found. Run `python ingest.py` first."
        )
    return Chroma(
        persist_directory=str(CHROMA_DB_DIR),
        embedding_function=get_embeddings(),
        collection_name=CHROMA_COLLECTION_NAME,
    )


def get_retriever(
    top_k: int = TOP_K,
    metadata_filter: Optional[Dict[str, Any]] = None,
) -> Any:
    """Build a retriever from the ChromaDB vector store.

    Args:
        top_k:           Number of documents to retrieve.
        metadata_filter: Optional ChromaDB metadata filter dict, e.g.
                         {"section_heading": "Admissions"}.

    Returns:
        LangChain retriever object.
    """
    vector_store = get_vector_store()
    search_kwargs: Dict[str, Any] = {"k": top_k}
    if metadata_filter:
        search_kwargs["filter"] = metadata_filter
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs=search_kwargs,
    )


def retrieve_chunks(
    query: str,
    top_k: int = TOP_K,
    metadata_filter: Optional[Dict[str, Any]] = None,
    debug: bool = False,
) -> List[Document]:
    """Retrieve the most relevant document chunks for *query*.

    Args:
        query:           User query string.
        top_k:           Number of chunks to return.
        metadata_filter: Optional ChromaDB filter.
        debug:           If True, log chunk previews.

    Returns:
        List of relevant Document objects.
    """
    retriever = get_retriever(top_k=top_k, metadata_filter=metadata_filter)
    docs = retriever.invoke(query)

    if debug:
        logger.debug("Retrieved %d chunks for query: '%s'", len(docs), query)
        for i, doc in enumerate(docs, 1):
            logger.debug(
                "  Chunk %d | %s | Page %s\n    %s…",
                i,
                doc.metadata.get("section_heading", "?"),
                doc.metadata.get("page", "?"),
                doc.page_content[:120].replace("\n", " "),
            )

    return docs


# ─────────────────────────────────────────────────────────────────────────────
#  Conversational RAG chain
# ─────────────────────────────────────────────────────────────────────────────

def _messages_to_pairs(messages: List[BaseMessage]) -> List[BaseMessage]:
    """Return the message list as-is (already in LangChain message format)."""
    return messages


def _to_tuple_history(messages: List[BaseMessage]) -> List[tuple]:
    """Convert LangChain message objects to (role, content) tuples.

    Some LangChain versions raise a '_type' serialization error when
    HumanMessage/AIMessage objects are passed directly to ChatPromptTemplate.
    Using plain tuples avoids this entirely.
    """
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append(("human", msg.content))
        elif isinstance(msg, AIMessage):
            result.append(("ai", msg.content))
    return result


def condense_question(
    question: str,
    chat_history: List[BaseMessage],
) -> str:
    """Rewrite a follow-up question to be self-contained.

    Args:
        question:     The latest user question.
        chat_history: List of prior HumanMessage / AIMessage objects.

    Returns:
        Standalone question string (unchanged if no history).
    """
    if not chat_history:
        return question

    llm = get_llm(streaming=False)
    chain = CONDENSE_QUESTION_PROMPT | llm | StrOutputParser()
    try:
        return chain.invoke(
            {"question": question, "chat_history": _to_tuple_history(chat_history)}
        )
    except Exception as exc:
        logger.warning("Question condensation failed (%s). Using original.", exc)
        return question


class RAGResponse:
    """Container for a RAG query result."""

    def __init__(
        self,
        answer: str,
        source_documents: List[Document],
        elapsed: float,
        condensed_question: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        self.answer = answer
        self.source_documents = source_documents
        self.elapsed = elapsed
        self.condensed_question = condensed_question
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens

    def get_citations(self) -> List[str]:
        """Return a deduplicated list of citation strings."""
        seen: set[str] = set()
        citations: List[str] = []
        for doc in self.source_documents:
            section = doc.metadata.get("section_heading", "General")
            page = doc.metadata.get("page", "N/A")
            citation = f"[{section} | Page {page}]"
            if citation not in seen:
                seen.add(citation)
                citations.append(citation)
        return citations


def query(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    top_k: int = TOP_K,
    metadata_filter: Optional[Dict[str, Any]] = None,
    debug: bool = False,
    user_name: Optional[str] = None,
) -> RAGResponse:
    """Run a full RAG query (retrieve → prompt → generate).

    Args:
        question:        User question.
        chat_history:    Conversation history (HumanMessage / AIMessage list).
        top_k:           Retrieval depth.
        metadata_filter: Optional ChromaDB metadata filter.
        debug:           Print retrieved chunks to logs.
        user_name:       Optional user name for personalised responses.

    Returns:
        RAGResponse with answer, citations, latency, and token info.
    """
    if chat_history is None:
        chat_history = []

    start = time.perf_counter()

    # 1. Condense follow-up questions into a standalone query
    standalone_q = condense_question(question, chat_history)
    logger.debug("Standalone question: %s", standalone_q)

    # 2. Retrieve relevant chunks
    docs = retrieve_chunks(
        standalone_q,
        top_k=top_k,
        metadata_filter=metadata_filter,
        debug=debug,
    )

    # 3. Build context string
    context = format_chunks_for_context(docs)

    # 4. Build personalised prompt and call the LLM
    prompt = build_rag_prompt(user_name=user_name)
    llm = get_llm(streaming=False)
    chain = prompt | llm | StrOutputParser()

    answer = chain.invoke(
        {
            "context": context,
            "question": question,
            "chat_history": _to_tuple_history(chat_history),
        }
    )

    elapsed = time.perf_counter() - start

    # 5. Estimate token usage
    prompt_tokens = estimate_tokens(context + question)
    completion_tokens = estimate_tokens(answer)

    return RAGResponse(
        answer=answer,
        source_documents=docs,
        elapsed=elapsed,
        condensed_question=standalone_q,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def stream_query(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    top_k: int = TOP_K,
    metadata_filter: Optional[Dict[str, Any]] = None,
    debug: bool = False,
    user_name: Optional[str] = None,
) -> Tuple[Generator[str, None, None], List[Document], float]:
    """Stream a RAG response token-by-token.

    Args:
        question:        User question.
        chat_history:    Prior conversation messages.
        top_k:           Retrieval depth.
        metadata_filter: Optional ChromaDB metadata filter.
        debug:           Log retrieved chunks.
        user_name:       Optional user name for personalised responses.

    Returns:
        Tuple of (token_generator, source_documents, retrieval_elapsed_seconds).
    """
    if chat_history is None:
        chat_history = []

    ret_start = time.perf_counter()

    standalone_q = condense_question(question, chat_history)
    docs = retrieve_chunks(
        standalone_q,
        top_k=top_k,
        metadata_filter=metadata_filter,
        debug=debug,
    )
    context = format_chunks_for_context(docs)
    retrieval_elapsed = time.perf_counter() - ret_start

    prompt = build_rag_prompt(user_name=user_name)
    llm = get_llm(streaming=True)
    chain = prompt | llm | StrOutputParser()

    def _token_gen() -> Generator[str, None, None]:
        yield from chain.stream(
            {
                "context": context,
                "question": question,
                "chat_history": _to_tuple_history(chat_history),
            }
        )

    return _token_gen(), docs, retrieval_elapsed


# ─────────────────────────────────────────────────────────────────────────────
#  Chat history helpers (for Streamlit session state)
# ─────────────────────────────────────────────────────────────────────────────

def build_chat_history(
    messages: List[Dict[str, str]],
) -> List[BaseMessage]:
    """Convert Streamlit session messages to LangChain message objects.

    Args:
        messages: List of dicts with keys "role" ("user"/"assistant") and
                  "content".

    Returns:
        List of HumanMessage / AIMessage objects.
    """
    history: List[BaseMessage] = []
    for msg in messages:
        if msg["role"] == "user":
            history.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            history.append(AIMessage(content=msg["content"]))
    return history
