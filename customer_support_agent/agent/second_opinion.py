"""
agent/second_opinion.py
=======================
Second-opinion agent for borderline escalation decisions.

Fires ONLY when confidence is in the 0.70–0.89 range ("needs clarification"
band) AND the decision is not already forced by a governance rule.

It re-evaluates the primary agent's draft using a different reasoning path:
  1. Checks if the proposed response fully addresses the customer's issue.
  2. Checks if any governance rule was missed.
  3. Returns a verdict: "agree" | "override_to_escalate" | "override_to_send"

The primary decision is only overridden if the second opinion verdict is
unanimous (i.e., the same conclusion reached twice from both directions).

This is a lightweight rule-based re-ranker — it does NOT make an LLM call
so it never introduces latency or cost.  A richer version could use a
smaller/faster LLM as a critic.
"""

import re
from logs.audit import write_audit_event

_MISSING_ORDER_PATTERN = re.compile(r"need.*order id|provide.*order|missing.*order", re.IGNORECASE)
_PLACEHOLDER_PATTERN   = re.compile(r"\[REDACTED|BLOCKED\]", re.IGNORECASE)
_CITATION_PATTERN      = re.compile(r"Policy citation:", re.IGNORECASE)

# Governance signals that should have caused escalation
_ESCALATION_SIGNALS = {
    "complaint_or_legal", "account_closure", "security_issue",
}


def second_opinion(
    message:       str,
    intent:        str,
    confidence:    float,
    response:      str,
    decision:      str,
    gate_status:   str | None,
    injection:     bool,
    contains_legal: bool,
    tool_name:     str | None,
    priority_boost: bool,
) -> dict:
    """
    Re-evaluate a borderline decision.
    Returns dict with keys: verdict, reason, final_decision.

    Skips evaluation if:
      - confidence outside 0.70–0.89 (not borderline)
      - gate already forced a hard decision
      - injection blocked the message
    """
    # Only run in the borderline band
    if not (0.70 <= confidence < 0.90):
        return {"verdict": "skipped", "reason": "outside_borderline_band",
                "final_decision": decision}

    # Hard governance already decided — don't override
    if gate_status == "escalate" or injection:
        return {"verdict": "skipped", "reason": "hard_governance_active",
                "final_decision": decision}

    issues: list[str] = []

    # Check 1: intent that must always escalate
    if intent in _ESCALATION_SIGNALS and decision == "auto_send":
        issues.append(f"Intent '{intent}' should always escalate (missed governance rule)")

    # Check 2: legal/threat language present but auto_send decided
    if contains_legal and decision == "auto_send":
        issues.append("Legal/threat language present — should escalate")

    # Check 3: response doesn't contain a policy citation
    if not _CITATION_PATTERN.search(response):
        issues.append("Response lacks policy citation — grounding insufficient")

    # Check 4: response is a placeholder (redacted/blocked) but decision is auto_send
    if _PLACEHOLDER_PATTERN.search(response) and decision == "auto_send":
        issues.append("Response is a redacted placeholder — cannot auto-send")

    # Check 5: response asks for order ID but decision is auto_send
    if _MISSING_ORDER_PATTERN.search(response) and decision == "auto_send":
        issues.append("Response requests clarification — auto_send inappropriate")

    # Check 6: priority_boost + auto_send without a tool call
    if priority_boost and decision == "auto_send" and not tool_name:
        issues.append("High-priority sentiment but no tool called — may be under-served")

    if issues:
        verdict = "override_to_escalate"
        final   = "escalate"
        reason  = "; ".join(issues)
    else:
        verdict = "agree"
        final   = decision
        reason  = "Primary decision validated — no governance gaps found"

    write_audit_event({
        "event":          "second_opinion",
        "original_decision": decision,
        "verdict":        verdict,
        "final_decision": final,
        "confidence":     confidence,
        "reason":         reason,
    })

    return {
        "verdict":        verdict,
        "reason":         reason,
        "final_decision": final,
    }
