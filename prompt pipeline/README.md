# ⚡ Prompt Pipeline

A production-quality, multi-stage LLM pipeline application built with **Python**, **Streamlit**, and the **OpenRouter API**. Every stage is a separate LLM call that accepts only the structured JSON output from the previous stage — no raw text ever crosses a stage boundary.

---

## ✨ Features

| Category | What's included |
|---|---|
| **Pipeline Tasks** | Support Ticket Triage · Essay Grader · Bug Report Triage · Meeting Notes to Actions · Recipe Adapter · Trip Planner |
| **Stage Architecture** | Stage 1 Extraction → Stage 2 Reasoning → Stage 3 Generation → Stage 4 Self-Critic |
| **Prompt Techniques** | Role Prompting, Structured Output, Chain-of-Thought, Goal-Oriented Prompting, Self-Critique |
| **OpenRouter Client** | httpx-based · model selection · retry with exponential back-off · JSON auto-repair |
| **Validation** | Pydantic v2 schemas for all 24 stage outputs (6 tasks × 4 stages) |
| **Logging** | Prompts, responses, latency, token usage, retry count — file + console |
| **Streamlit UI** | Dark theme · sidebar config · stage panels · JSON viewers · execution timeline · progress bar · download JSON/TXT · session history |
| **Sample Inputs** | 3 real-world + 1 broken input per task (24 samples total) |

---

## 🗂 Project Structure

```
prompt pipeline/
│
├── app.py                  # Main Streamlit entry point
├── app_sidebar.py          # Sidebar rendering (model + task + sample select)
├── app_downloads.py        # Download JSON / TXT helpers
├── config.py               # Central config (env vars, models, task metadata)
│
├── pipeline/
│   ├── __init__.py
│   └── engine.py           # PipelineEngine — orchestrates all 4 stages
│
├── prompts/
│   ├── __init__.py
│   ├── support_triage.py   # Prompts for Support Ticket Triage
│   ├── essay_grader.py     # Prompts for Essay Grader
│   ├── bug_triage.py       # Prompts for Bug Report Triage
│   ├── meeting_notes.py    # Prompts for Meeting Notes to Actions
│   ├── recipe_adapter.py   # Prompts for Recipe Adapter
│   └── trip_planner.py     # Prompts for Trip Planner
│
├── schemas/
│   └── __init__.py         # Pydantic schemas for all 6 tasks × 4 stages
│
├── services/
│   ├── __init__.py
│   └── openrouter_client.py  # OpenRouter API client + StageResult
│
├── utils/
│   ├── __init__.py
│   ├── formatters.py       # format_json, format_duration, truncate
│   ├── validators.py       # API key + input validation
│   └── sample_inputs.py    # 24 sample inputs (3 real + 1 broken per task)
│
├── assets/
│   ├── __init__.py
│   ├── styles.py           # Custom CSS (dark professional theme)
│   └── components.py       # Reusable Streamlit HTML components
│
├── logs/
│   └── pipeline.log        # Auto-created; detailed execution logs
│
├── .env.example            # Template for environment variables
├── requirements.txt        # Pinned dependencies
└── README.md               # This file
```

---

## 🚀 Quick Start

### 1. Clone / download the project

```bash
cd "prompt pipeline"
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
copy .env.example .env      # Windows
cp  .env.example  .env      # macOS / Linux
```

Then edit `.env` and add your OpenRouter API key:

```env
OPENROUTER_API_KEY=sk-or-your-key-here
DEFAULT_MODEL=openai/gpt-4o-mini
```

Get a free API key at **[openrouter.ai](https://openrouter.ai)**.

### 5. Run the app

```bash
streamlit run app.py
```

The app opens at **http://localhost:8501**

---

## 🔑 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | *(required)* | Your OpenRouter API key |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API base URL |
| `OPENROUTER_REFERER` | `https://prompt-pipeline-app` | HTTP Referer header |
| `OPENROUTER_APP_TITLE` | `Prompt Pipeline` | X-Title header |
| `DEFAULT_MODEL` | `openai/gpt-4o-mini` | Default model slug |
| `REQUEST_TIMEOUT` | `60` | HTTP timeout in seconds |
| `MAX_RETRIES` | `3` | Max JSON-parse retry attempts |
| `RETRY_DELAY` | `2.0` | Base delay between retries (s) |
| `MAX_TOKENS` | `2048` | Max tokens per LLM call |
| `TEMPERATURE` | `0.3` | Sampling temperature |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING) |

---

## 🤖 Available Models

| Display Name | Slug |
|---|---|
| GPT-4o Mini *(default)* | `openai/gpt-4o-mini` |
| GPT-4o | `openai/gpt-4o` |
| Claude 3.5 Haiku | `anthropic/claude-3-5-haiku` |
| Claude 3.5 Sonnet | `anthropic/claude-3-5-sonnet` |
| Gemini Flash 1.5 | `google/gemini-flash-1.5` |
| Llama 3.1 8B *(free)* | `meta-llama/llama-3.1-8b-instruct:free` |
| Mistral 7B *(free)* | `mistralai/mistral-7b-instruct:free` |

Switch models at any time using the sidebar dropdown — no restart needed.

---

## 🔬 Pipeline Architecture

### Stage Flow

```
Raw Text Input
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 1 — Extraction                                   │
│  Role Prompting + Structured Output                     │
│  → Parses raw input into structured JSON fields         │
└────────────────────────┬────────────────────────────────┘
                         │ JSON only
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 2 — Reasoning                                    │
│  Chain-of-Thought (step-by-step reasoning_chain)        │
│  → Classifies, prioritises, analyses — returns JSON     │
└────────────────────────┬────────────────────────────────┘
                         │ JSON only
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 3 — Generation                                   │
│  Goal-Oriented Prompting with explicit constraints      │
│  → Produces final human-readable + structured output    │
└────────────────────────┬────────────────────────────────┘
                         │ JSON only
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 4 — Self-Critic                                  │
│  Reviews output, scores 0-10                            │
│  If score < 7.0 → regenerates Stage 3 output           │
│  Returns final_output (improved or original)            │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
                  Final Output
```

### JSON Passing Contract

- Each stage prompt template contains `{stage1_json}`, `{stage2_json}`, etc. as placeholders.
- The engine fills those with `json.dumps(parsed_output, indent=2)` — never raw text.
- If a stage fails JSON parsing, the client automatically retries up to `MAX_RETRIES` times, appending a repair instruction to the conversation.

### Pydantic Validation

Every stage output is validated against its corresponding schema in `schemas/__init__.py`. Validation failures are non-blocking — a warning is logged and the pipeline continues. This prevents a single field error from halting the run.

---

## 🎫 Pipeline Tasks

### 1. Support Ticket Triage
Classifies customer support tickets by category, priority (P1–P4), and routes them to the right team. Stage 4 checks tone and accuracy of the suggested reply.

### 2. Essay Grader
Evaluates student essays on a 100-point rubric across four dimensions (Content, Organisation, Style, Mechanics) and produces student-facing feedback with specific improvement suggestions.

### 3. Bug Report Triage
Parses bug reports, assigns severity (critical/major/minor/trivial), identifies root cause hypothesis, and generates a structured ticket with fix estimates and labels.

### 4. Meeting Notes to Actions
Converts raw meeting notes into structured action items (with owners, due dates, priorities), decisions, open questions, and a ready-to-send email summary.

### 5. Recipe Adapter
Analyses dietary restrictions, identifies conflicting ingredients, finds culinary substitutions, and produces a complete adapted recipe with chef tips and nutrition estimates.

### 6. Trip Planner
Extracts trip requirements, plans logistics and attractions, and generates a full day-by-day itinerary with budget breakdowns, packing list, and practical info.

---

## 💥 Broken Input Demo

Each task includes one intentionally broken or underdefined input to demonstrate graceful handling:

| Task | Broken Input |
|---|---|
| Support Triage | `"asdfjkl; ??? ### ... ok bye lol 👍"` |
| Essay Grader | `"ok"` (too short) |
| Bug Report | `"something is broken please fix it"` |
| Meeting Notes | `"we talked about stuff and things will happen"` |
| Recipe Adapter | `"make it healthy please thanks"` |
| Trip Planner | Contradictory constraints (everywhere, 1 day, $0, no transport) |

The pipeline does not crash — Stage 1 attempts extraction with low confidence, and the self-critic (Stage 4) flags the quality issues in `issues_found`.

---

## 📊 Transparency & Observability

The UI displays for every stage:
- **JSON Output** — syntax-highlighted, scrollable
- **System + User Prompts** — toggle open/closed
- **Raw LLM Response** — the exact API response text
- **Execution Time** — per stage and total
- **Retry Count** — shows how many JSON-parse retries were needed
- **Token Usage** — prompt + completion + total

All of this is also written to `logs/pipeline.log`.

---

## 💾 Export

After any run you can download:
- **JSON** — full pipeline result including all stage data, prompts, and metadata
- **TXT** — human-readable summary with all stage outputs

---

## 🚢 Deployment

### Streamlit Community Cloud (free)

1. Push the project to a public GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo.
3. Set the main file to `app.py`.
4. Add your `OPENROUTER_API_KEY` and other env vars in **Secrets** (Settings → Secrets):

```toml
OPENROUTER_API_KEY = "sk-or-..."
DEFAULT_MODEL = "openai/gpt-4o-mini"
```

**Important:** Do not commit your `.env` file — add it to `.gitignore`.

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

```bash
docker build -t prompt-pipeline .
docker run -p 8501:8501 -e OPENROUTER_API_KEY=sk-or-... prompt-pipeline
```

### Environment notes
- Python 3.10+ required (uses `match` statement in Pydantic internals)
- No GPU needed — all inference is remote via OpenRouter
- No database, no vector store, no external storage

---

## 🧪 Running Tests (Manual)

1. Load a sample input from the sidebar (e.g., "✅ Sample 1 — Billing Issue").
2. Click **Run Pipeline**.
3. Verify all 4 stages complete with green ✓ badges.
4. Load the "💥 Broken Input" sample and verify graceful handling (pipeline completes, Stage 4 shows low quality score and issues_found list).

---

## 📋 Dependencies

| Package | Version | Purpose |
|---|---|---|
| `streamlit` | 1.35.0 | Web UI framework |
| `httpx` | 0.27.0 | Async-capable HTTP client |
| `pydantic` | 2.7.1 | Data validation and schemas |
| `python-dotenv` | 1.0.1 | .env file loading |
| `typing-extensions` | 4.11.0 | Python 3.9 compatibility |

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

*Built as a demonstration of multi-stage prompt engineering patterns using only the OpenRouter API — no RAG, no vector databases, no agents, no external tools.*
