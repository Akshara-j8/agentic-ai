"""
eval/kpi_report.py
==================
Reads logs/audit.jsonl and computes the three key KPIs used as proxies for
the Day 8 dashboard:

  auto_resolve_rate      – % of agent_decision events with decision="auto_send"
                           (proxy for first-contact resolution / deflection rate)
  escalation_rate        – % of agent_decision events with decision="escalate"
  correct_escalation_rate– % of escalations that were triggered by a known
                           governance rule (legal/threat, cap breach, injection)
  avg_confidence_auto    – average confidence on auto-resolved tickets only
  injection_rate         – % of all agent_decision events that had
                           injection_detected=True

Prints a formatted summary table to stdout.

Run
---
    python eval/kpi_report.py
    python eval/kpi_report.py --log path/to/audit.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Locate the default audit log
# ---------------------------------------------------------------------------
_DEFAULT_LOG = Path(__file__).resolve().parents[1] / "logs" / "audit.jsonl"

# Governance reasons that constitute a *correct* escalation
_GOVERNANCE_REASONS = {
    "legal_or_threat_language",
    "account_closure_requires_human",
    "credit_over_goodwill_cap",
}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_events(log_path: Path) -> list[dict[str, Any]]:
    """Return all JSON objects from an audit JSONL file."""
    if not log_path.exists():
        print(f"[kpi_report] WARNING: log file not found at {log_path}", file=sys.stderr)
        return []
    events = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f"[kpi_report] Skipping malformed line: {exc}", file=sys.stderr)
    return events


# ---------------------------------------------------------------------------
# KPI computation
# ---------------------------------------------------------------------------

def compute_kpis(events: list[dict[str, Any]]) -> dict[str, Any]:
    decision_events = [e for e in events if e.get("event") == "agent_decision"]
    injection_events = [e for e in events if e.get("event") == "flagged_injection_attempt"]

    total = len(decision_events)
    if total == 0:
        return {
            "total_decisions": 0,
            "auto_resolved": 0,
            "escalated": 0,
            "refused": 0,
            "auto_resolve_rate": 0.0,
            "escalation_rate": 0.0,
            "refusal_rate": 0.0,
            "correct_escalation_rate": None,
            "avg_confidence_auto": None,
            "injection_events": len(injection_events),
            "injection_rate": 0.0,
        }

    auto_events = [e for e in decision_events if e.get("decision") == "auto_send"]
    esc_events = [e for e in decision_events if e.get("decision") == "escalate"]
    refuse_events = [e for e in decision_events if e.get("decision") == "refuse"]

    # Correct escalation: escalation triggered by a known governance rule
    governed_escalations = [
        e for e in esc_events
        if e.get("gate_reason") in _GOVERNANCE_REASONS
        or e.get("injection_detected") is True
    ]
    correct_esc_rate = (
        len(governed_escalations) / len(esc_events) if esc_events else None
    )

    # Average confidence on auto-resolved tickets
    conf_values = [e["confidence"] for e in auto_events if "confidence" in e]
    avg_conf = sum(conf_values) / len(conf_values) if conf_values else None

    # Injection rate (injections / total decisions)
    injections_in_decisions = sum(
        1 for e in decision_events if e.get("injection_detected") is True
    )

    return {
        "total_decisions": total,
        "auto_resolved": len(auto_events),
        "escalated": len(esc_events),
        "refused": len(refuse_events),
        "auto_resolve_rate": len(auto_events) / total,
        "escalation_rate": len(esc_events) / total,
        "refusal_rate": len(refuse_events) / total,
        "correct_escalation_rate": correct_esc_rate,
        "avg_confidence_auto": avg_conf,
        "injection_events": len(injection_events),
        "injection_rate": injections_in_decisions / total,
    }


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _pct(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


def _conf(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.3f}"


def print_table(kpis: dict[str, Any]) -> None:
    col_w = 42
    val_w = 12
    sep = "─" * (col_w + val_w + 5)

    print(f"\n{'Support Copilot – KPI Summary':^{col_w + val_w + 5}}")
    print(sep)
    print(f"  {'Metric':<{col_w}} {'Value':>{val_w}}")
    print(sep)

    rows = [
        ("Total agent decisions", str(kpis["total_decisions"])),
        ("  Auto-resolved", str(kpis["auto_resolved"])),
        ("  Escalated", str(kpis["escalated"])),
        ("  Refused (out-of-scope / injection)", str(kpis["refused"])),
        ("─" * col_w, "─" * val_w),
        ("Auto-resolve rate  [↑ target > 70%]", _pct(kpis["auto_resolve_rate"])),
        ("Escalation rate    [↓ target < 20%]", _pct(kpis["escalation_rate"])),
        ("Refusal rate", _pct(kpis["refusal_rate"])),
        ("Correct-escalation rate [↑ target 100%]", _pct(kpis["correct_escalation_rate"])),
        ("Avg confidence on auto-resolved  [↑]", _conf(kpis["avg_confidence_auto"])),
        ("─" * col_w, "─" * val_w),
        ("Total injection events logged", str(kpis["injection_events"])),
        ("Injection rate (decisions flagged)", _pct(kpis["injection_rate"])),
    ]

    for metric, value in rows:
        if metric.startswith("─"):
            print(f"  {metric}─{value}")
        else:
            print(f"  {metric:<{col_w}} {value:>{val_w}}")

    print(sep)
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Compute KPIs from audit.jsonl")
    parser.add_argument(
        "--log",
        type=Path,
        default=_DEFAULT_LOG,
        help=f"Path to audit.jsonl (default: {_DEFAULT_LOG})",
    )
    args = parser.parse_args()

    events = load_events(args.log)
    if not events:
        print("No audit events found. Run the agent or the eval suite first.")
        sys.exit(1)

    kpis = compute_kpis(events)
    print_table(kpis)


if __name__ == "__main__":
    main()
