# Support Copilot

An AI-powered customer support agent that resolves, escalates, or refuses tickets using a deterministic LangGraph pipeline, RAG-backed policy retrieval, and a governance layer — no hallucination, no policy bypass.

---

## Architecture

```
Ticket body (untrusted)
       │
       ▼
[Injection Guard]        ← detects override patterns; sanitises input; logs to audit.jsonl
       │
       ▼
[Intent Classifier]      ← rule-based: order_status · late_delivery_credit · refund_request
       │                    complaint_or_legal · out_of_scope · security_issue · …
       ▼
[RAG Retrieval]          ← ChromaDB vector search over 4 policy docs (refund, returns,
       │                    escalation, account-security); top-5 chunks ranked by cosine similarity
       ▼
[Human Gate]             ← blocks auto-action if: legal/threat language detected,
       │                    amount > $10 goodwill cap, or account closure requested
       ▼
[Tool Calls]             ← order_lookup · apply_credit · create_ticket
       │                    all tool events audited to logs/audit.jsonl
       ▼
[Draft Resolution]       ← builds response with policy citation; injection-blocked tickets
       │                    get a fixed safe reply
       ▼
[Decide: auto_send / escalate / refuse]
```

**Tools**
- `order_lookup` — reads `data/orders.json`; returns status, carrier, ETA
- `apply_credit` — applies goodwill credit ≤ $10; above cap → escalate
- `create_ticket` — creates high-priority escalation record

**RAG**
Policy documents in `data/policies/` are chunked, embedded with `sentence-transformers/all-MiniLM-L6-v2`, and stored in ChromaDB. Every response cites the top-matching policy clause.

**Governance**
Three gates block automated action: threat/legal language, credit above the $10 cap, and account-closure requests. Prompt injections are caught before classification and result in a `refuse` decision with the attempt logged.

**Eval suite** (`eval/scenarios.py`)
Five scenarios cover the full decision surface: order-status happy path, within-policy credit, $300-refund + threat escalation, competitor refusal, and prompt injection. Each run checks intent, tool call, output content, gate behaviour, and policy citation. Run with `python eval/scenarios.py`.

**KPI report** (`eval/kpi_report.py`)
Reads `logs/audit.jsonl` and prints auto-resolve rate, escalation rate, correct-escalation rate, average confidence on auto-resolved tickets, and injection rate. Run with `python eval/kpi_report.py`.

---

## Quick Start

```bash
pip install -r requirements.txt
python rag/ingest.py          # build ChromaDB index
streamlit run ui/streamlit_app.py   # interactive UI
python eval/scenarios.py      # run eval suite
python eval/kpi_report.py     # print KPI table
```
