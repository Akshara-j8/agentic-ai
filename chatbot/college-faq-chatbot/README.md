# 🎓 BVRITH College FAQ Chatbot

A production-quality Retrieval-Augmented Generation (RAG) chatbot built for
**B V Raju Institute of Technology and Higher Sciences (BVRITH)**.

Ask any question about admissions, fees, courses, placements, facilities, and
more — every answer is sourced exclusively from the official knowledge base.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔍 Retrieval | ChromaDB vector search — top-5 most relevant chunks |
| 🧠 LLM | GPT-4o-mini via OpenRouter |
| 📎 Citations | Every answer shows `[Section | Page N]` source references |
| 💬 Memory | Multi-turn conversation with follow-up support |
| 🌊 Streaming | Token-by-token typing animation |
| 📊 Dashboard | RAGAS metrics — Faithfulness, Relevancy, Precision, Recall |
| 📈 Charts | Interactive Plotly bar + radar charts |
| 🔒 Grounded | Never answers from training data — only the knowledge base |

---

## 🗂️ Project Structure

```
college-faq-chatbot/
│
├── app.py              ← Streamlit UI (Chat + Dashboard)
├── ingest.py           ← Document ingestion pipeline
├── rag.py              ← RAG chain, retriever, streaming
├── prompts.py          ← System prompt + question-rewriter
├── evaluator.py        ← RAGAS evaluation pipeline
├── config.py           ← All constants and env vars
├── utils.py            ← Logging, timers, text helpers
├── requirements.txt    ← Python dependencies
├── README.md           ← This file
├── .env.example        ← Environment variable template
│
├── data/
│   └── knowledge_base.docx   ← Source of truth (DO NOT DELETE)
│
├── chroma_db/          ← Persisted ChromaDB vectors (auto-created)
├── test_cases/         ← Auto-generated RAGAS test cases
└── evaluation/
    └── report.json     ← RAGAS evaluation report
```

---

## ⚙️ Installation

### 1. Clone / download the project

```bash
cd college-faq-chatbot
```

### 2. Create and activate a virtual environment (recommended)

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 🔑 API Key Setup

Copy the template and fill in your real keys:

```bash
cp .env.example .env
```

Open `.env` and set **both** keys:

```env
# OpenAI — required for embeddings (text-embedding-3-small)
# OpenRouter does NOT support the /v1/embeddings endpoint.
OPENAI_API_KEY=sk-...your_openai_key...

# OpenRouter — required for the chat LLM (gpt-4o-mini)
OPENROUTER_API_KEY=sk-or-v1-...your_openrouter_key...
```

| Key | Purpose | Where to get it |
|---|---|---|
| `OPENAI_API_KEY` | Embeddings via `text-embedding-3-small` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `OPENROUTER_API_KEY` | LLM (GPT-4o-mini) | [openrouter.ai/keys](https://openrouter.ai/keys) |

> **Why two keys?**
> OpenRouter is a unified LLM gateway but it does **not** expose an
> `/v1/embeddings` endpoint. Vector creation and retrieval therefore call
> OpenAI directly, while all chat completions go through OpenRouter.

---

## 🚀 Quick Start

### Step 1 — Ingest the knowledge base

This only needs to run once. If `chroma_db/` already exists it will skip
re-ingestion automatically.

```bash
python ingest.py
```

Expected output:

```
2026-07-03 19:00:00 | ingest | INFO | Loading document: data/knowledge_base.docx
2026-07-03 19:00:01 | ingest | INFO | Split into 312 chunks (size=500, overlap=50)
2026-07-03 19:00:15 | ingest | INFO | Ingestion complete in 14.32s. Total chunks stored: 312

✅  Ingestion complete. 312 chunks stored in ChromaDB.
```

### Step 2 — Start the chatbot

```bash
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 💬 Chat Interface

- Type any question in the input box.
- Answers stream token-by-token with a typing animation.
- Citations appear as coloured badges below each answer.
- Latency, chunk count, and approximate token usage are shown per response.
- Toggle **"Show retrieved chunks"** in the sidebar to inspect raw retrieval.
- Click **🗑️ Clear** to start a fresh conversation.

**Unknown questions** return:

> "This information is not available in the uploaded knowledge base."

---

## 📊 Evaluation

### Run RAGAS evaluation

```bash
python evaluator.py
```

Or click **▶️ Run Evaluation** inside the Dashboard page.

This will:
1. Auto-generate 10 test question-answer pairs from random knowledge base chunks.
2. Run the full RAG pipeline on each question.
3. Score with four RAGAS metrics (requires `OPENAI_API_KEY`).
4. Save results to `evaluation/report.json`.

### RAGAS Metrics

| Metric | What it measures | Target |
|---|---|---|
| **Faithfulness** | Is the answer grounded in the retrieved context? | ≥ 0.7 |
| **Answer Relevancy** | Is the answer relevant to the question? | ≥ 0.7 |
| **Context Precision** | Are the retrieved chunks precise and non-noisy? | ≥ 0.7 |
| **Context Recall** | Do the chunks contain all info needed to answer? | ≥ 0.7 |

### Custom test cases

Create a JSON file and pass it to the evaluator:

```json
[
  {
    "question": "What is the annual tuition fee for B.Tech?",
    "ground_truth": "The annual tuition fee for B.Tech is ..."
  }
]
```

```bash
python evaluator.py --test-cases test_cases/my_cases.json
```

---

## 🛠️ Configuration

All settings live in `config.py` and can be overridden via `.env`:

| Variable | Default | Description |
|---|---|---|
| `CHUNK_SIZE` | `500` | Characters per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `TOP_K` | `5` | Retrieved chunks per query |
| `LLM_MODEL` | `openai/gpt-4o-mini` | OpenRouter model |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |

---

## 🐛 Troubleshooting

| Symptom | Fix |
|---|---|
| `OPENAI_API_KEY not set` | Add `OPENAI_API_KEY` to your `.env` file |
| `OPENROUTER_API_KEY not set` | Add `OPENROUTER_API_KEY` to your `.env` file |
| `Vector store not found` | Run `python ingest.py` |
| `knowledge_base.docx not found` | Place the DOCX in `data/knowledge_base.docx` |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Answer says "not available" | The question topic may not be in the knowledge base |
| RAGAS evaluation slow | Normal — each question makes multiple LLM calls |

---

## 📦 Tech Stack

- **Python 3.11+**
- **LangChain** — RAG orchestration
- **ChromaDB** — vector persistence
- **Streamlit** — web UI
- **OpenAI** — `text-embedding-3-small` embeddings
- **OpenRouter** — GPT-4o-mini completions
- **RAGAS** — RAG evaluation framework
- **Plotly** — interactive charts

---

## 📄 License

MIT — feel free to adapt for your institution.
