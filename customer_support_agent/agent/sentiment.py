"""
agent/sentiment.py
==================
Rule-based sentiment analyser and priority escalator.
No LLM call — pure lexicon + pattern matching so it never slows the pipeline.

Outputs added to AgentState:
  sentiment       : "positive" | "neutral" | "negative" | "hostile"
  sentiment_score : float  -1.0 (hostile) … +1.0 (positive)
  priority_boost  : bool   True when sentiment warrants expedited handling

Priority boost rules (additive, any one fires it):
  - sentiment == "hostile"
  - contains_legal_or_threat already True
  - sentiment_score < -0.5 AND intent is refund/missing/complaint
"""

import re
from logs.audit import write_audit_event

# ── Lexicons ───────────────────────────────────────────────────────────────
_HOSTILE = re.compile(
    r"\b(sue|lawyer|attorney|chargeback|fraud|scam|incompetent|useless|"
    r"furious|outrageous|unacceptable|disgusting|pathetic|worst|terrible|"
    r"never.again|report you|escalate this|demand|immediately|right now|"
    r"this is ridiculous|absolute joke)\b",
    re.IGNORECASE,
)

_NEGATIVE = re.compile(
    r"\b(angry|frustrated|disappointed|unhappy|upset|annoyed|delayed|late|"
    r"missing|wrong|broken|damaged|not received|still waiting|no update|"
    r"problem|issue|complaint|refund|overcharged|double.charged)\b",
    re.IGNORECASE,
)

_POSITIVE = re.compile(
    r"\b(thank|thanks|please|appreciate|great|good|happy|love|wonderful|"
    r"helpful|quick|resolved|sorted|perfect|excellent|amazing)\b",
    re.IGNORECASE,
)

# Intensifiers multiply the base score
_INTENSIFIER = re.compile(
    r"\b(very|extremely|absolutely|completely|totally|really|so|so much|"
    r"beyond|utterly)\b",
    re.IGNORECASE,
)

_HIGH_PRIORITY_INTENTS = {
    "refund_request", "missing_delivery", "complaint_or_legal",
    "account_closure", "security_issue",
}


def analyse_sentiment(message: str, intent: str, contains_legal: bool) -> dict:
    """
    Analyse *message* and return a sentiment dict.
    Pure lexicon — fast, deterministic, no external calls.
    """
    hostile_hits  = len(_HOSTILE.findall(message))
    negative_hits = len(_NEGATIVE.findall(message))
    positive_hits = len(_POSITIVE.findall(message))
    intensifiers  = len(_INTENSIFIER.findall(message))
    intensity     = 1.0 + 0.3 * min(intensifiers, 3)   # cap at ×1.9

    raw = (positive_hits - negative_hits * 1.5 - hostile_hits * 3.0) * intensity

    # Normalise to -1 … +1
    score = max(-1.0, min(1.0, raw / 10.0))

    if hostile_hits > 0:
        label = "hostile"
    elif score < -0.15:
        label = "negative"
    elif score > 0.1:
        label = "positive"
    else:
        label = "neutral"

    priority_boost = (
        label == "hostile"
        or contains_legal
        or (score < -0.5 and intent in _HIGH_PRIORITY_INTENTS)
    )

    write_audit_event({
        "event":          "sentiment_analysis",
        "sentiment":      label,
        "sentiment_score": round(score, 3),
        "priority_boost": priority_boost,
        "hostile_hits":   hostile_hits,
        "negative_hits":  negative_hits,
        "positive_hits":  positive_hits,
    })

    return {
        "sentiment":       label,
        "sentiment_score": round(score, 3),
        "priority_boost":  priority_boost,
    }
