import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from agent.injection_guard import screen_message
from agent.sentiment import analyse_sentiment
from agent.second_opinion import second_opinion
from agent.translator import process_incoming, translate_response
from logs.audit import write_audit_event
from rag.retrieve import retrieve
from tools.apply_credit import GOODWILL_CREDIT_CAP, apply_credit
from tools.create_ticket import create_ticket
from tools.order_lookup import order_lookup


Intent = Literal[
    "order_status",
    "late_delivery_credit",
    "refund_request",
    "missing_delivery",
    "cancelled_order",
    "security_issue",
    "complaint_or_legal",
    "account_closure",
    "out_of_scope",
    "general_support",
]

LEGAL_OR_THREAT_PATTERN = re.compile(
    r"\b(legal|lawyer|attorney|lawsuit|sue|subpoena|regulator|chargeback|complaint|"
    r"report (?:you|the company)|corporate|threat|fraud|unauthorized)\b",
    re.IGNORECASE,
)
ORDER_ID_PATTERN = re.compile(r"\bORD-\d{4}\b", re.IGNORECASE)
MONEY_PATTERN = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)|(?:\b(\d+(?:\.\d{1,2})?)\s*(?:usd|dollars)\b)", re.IGNORECASE)
COMPETITOR_PATTERN = re.compile(r"\b(competitor|amazon|walmart|target|best buy|shopify|which .* better)\b", re.IGNORECASE)


class AgentState(TypedDict, total=False):
    message: str
    injection_detected: bool
    intent: Intent
    order_id: str | None
    requested_credit_amount: float | None
    contains_legal_or_threat: bool
    policy_context: list[dict[str, Any]]
    tool_name: str | None
    tool_output: dict[str, Any] | None
    confidence: float
    decision: Literal["auto_send", "escalate", "refuse"]
    gate_status: Literal["allow", "escalate"]
    gate_reason: str | None
    response: str
    # ── Stretch: sentiment ──────────────────────────────────────
    sentiment: str | None               # "positive"|"neutral"|"negative"|"hostile"
    sentiment_score: float | None       # -1.0 … +1.0
    priority_boost: bool                # True → expedited queue
    # ── Stretch: second opinion ─────────────────────────────────
    second_opinion_verdict: str | None  # "agree"|"override_to_escalate"|"skipped"
    second_opinion_reason: str | None
    # ── Stretch: multilingual ───────────────────────────────────
    detected_language: str | None       # ISO-639-1 code
    translated_to_english: bool         # True if input was translated
    original_message: str | None        # preserved original before translation


def _extract_order_id(message: str) -> str | None:
    match = ORDER_ID_PATTERN.search(message)
    return match.group(0).upper() if match else None


def _extract_amount(message: str) -> float | None:
    amounts = []
    for match in MONEY_PATTERN.finditer(message):
        value = match.group(1) or match.group(2)
        if value:
            amounts.append(float(value))
    return max(amounts) if amounts else None


def _classify_intent(message: str) -> Intent:
    text = message.lower()
    if COMPETITOR_PATTERN.search(message):
        return "out_of_scope"
    if LEGAL_OR_THREAT_PATTERN.search(message):
        return "complaint_or_legal"
    if ("close" in text or "delete" in text or "deactivate" in text) and "account" in text:
        return "account_closure"
    if any(term in text for term in ["password", "hacked", "account takeover", "login", "unauthorized"]):
        return "security_issue"
    if "missing" in text or "not received" in text or "never arrived" in text:
        return "missing_delivery"
    if "cancel" in text:
        return "cancelled_order"
    if "late" in text or "delay" in text or "delayed" in text:
        if "credit" in text or "goodwill" in text or "$" in text:
            return "late_delivery_credit"
        return "order_status"
    if "refund" in text or "double" in text or "charged" in text or "credit" in text:
        return "refund_request"
    if "order" in text or _extract_order_id(message):
        return "order_status"
    return "general_support"


def _policy_query(state: AgentState) -> str:
    intent = state["intent"]
    message = state["message"]
    if intent == "complaint_or_legal":
        return "legal action complaint language always escalates"
    if intent == "late_delivery_credit":
        return "goodwill credit cap $10 carrier delay"
    if intent == "refund_request":
        return "refund over $50 approval double charge"
    if intent == "missing_delivery":
        return "delivered but missing refund lost order"
    if intent == "security_issue":
        return "account security unauthorized access escalate"
    if intent == "account_closure":
        return "account closure request escalation account status"
    if intent == "out_of_scope":
        return "support policy escalation notes"
    return message


def _best_policy_clause(state: AgentState) -> dict[str, Any]:
    context = state.get("policy_context") or []
    if not context:
        return {
            "source": "unavailable",
            "clause": "unavailable",
            "title": "No policy context",
            "text": "No policy context was retrieved.",
        }

    intent = state["intent"]
    preferred_clauses = {
        "complaint_or_legal": ["ES-1", "ES-2"],
        "late_delivery_credit": ["GW-2", "GW-1", "GW-3"],
        "refund_request": ["RF-4", "ES-4", "RF-3"],
        "missing_delivery": ["RF-1", "RT-7"],
        "cancelled_order": ["RF-1"],
        "security_issue": ["AS-6", "AS-1"],
        "account_closure": ["AS-1", "AS-7"],
        "out_of_scope": ["ES-7"],
    }.get(intent, [])

    for clause in preferred_clauses:
        for chunk in context:
            if chunk.get("clause") == clause:
                return chunk
    return context[0]


def screen_for_injection_node(state: AgentState) -> AgentState:
    """Treat the ticket body as untrusted data; sanitise before further processing."""
    result = screen_message(state["message"])
    updates: AgentState = {"injection_detected": result["injection_detected"]}
    if result["injection_detected"]:
        # Replace the message so no downstream node ever sees the injected text.
        updates["message"] = result["sanitised_message"]
    return updates


def classify_intent_node(state: AgentState) -> AgentState:
    message = state["message"]
    return {
        "intent": _classify_intent(message),
        "order_id": _extract_order_id(message),
        "requested_credit_amount": _extract_amount(message),
        "contains_legal_or_threat": bool(LEGAL_OR_THREAT_PATTERN.search(message)),
    }


def retrieve_policy_context_node(state: AgentState) -> AgentState:
    return {"policy_context": retrieve(_policy_query(state), k=5)}


def gate_sensitive_action_node(state: AgentState) -> AgentState:
    intent = state["intent"]
    message = state["message"]
    amount = state.get("requested_credit_amount")
    reason = None

    if state.get("contains_legal_or_threat"):
        reason = "legal_or_threat_language"
    elif intent == "account_closure":
        reason = "account_closure_requires_human"
    elif amount is not None and amount > GOODWILL_CREDIT_CAP:
        reason = "credit_over_goodwill_cap"

    if reason is None:
        return {"gate_status": "allow", "gate_reason": None}

    ticket = create_ticket(
        summary=f"Human follow-up required ({reason}): {message[:160]}",
        category="escalation",
        priority="high",
    )
    return {
        "gate_status": "escalate",
        "gate_reason": reason,
        "tool_name": "create_ticket",
        "tool_output": ticket.model_dump(),
    }


def call_relevant_tool_node(state: AgentState) -> AgentState:
    intent = state["intent"]
    message = state["message"]
    order_id = state.get("order_id")
    amount = state.get("requested_credit_amount")
    contains_legal = state.get("contains_legal_or_threat", False)

    if state.get("gate_status") == "escalate":
        return {"tool_name": state.get("tool_name"), "tool_output": state.get("tool_output")}

    if intent == "out_of_scope":
        return {"tool_name": None, "tool_output": None}

    if contains_legal:
        ticket = create_ticket(
            summary=f"Escalation required: {message[:180]}",
            category="escalation",
            priority="high",
        )
        return {"tool_name": "create_ticket", "tool_output": ticket.model_dump()}

    if intent in {"order_status", "late_delivery_credit", "refund_request", "missing_delivery", "cancelled_order"} and order_id:
        lookup = order_lookup(order_id)
        tool_output = lookup.model_dump()
        tool_name = "order_lookup"

        if intent == "late_delivery_credit":
            credit_amount = amount if amount is not None else GOODWILL_CREDIT_CAP
            if credit_amount <= GOODWILL_CREDIT_CAP:
                credit = apply_credit(order_id, credit_amount, "Goodwill credit for delivery delay")
                tool_output = {"order_lookup": tool_output, "apply_credit": credit.model_dump()}
                tool_name = "order_lookup+apply_credit"
            else:
                ticket = create_ticket(
                    summary=f"Credit request over goodwill cap for {order_id}: ${credit_amount:.2f}",
                    category="escalation",
                    priority="high",
                )
                tool_output = {"order_lookup": tool_output, "create_ticket": ticket.model_dump()}
                tool_name = "order_lookup+create_ticket"

        return {"tool_name": tool_name, "tool_output": tool_output}

    if intent in {"refund_request", "missing_delivery", "security_issue", "general_support"}:
        category = "security" if intent == "security_issue" else "general"
        priority = "high" if intent in {"security_issue", "missing_delivery"} else "normal"
        ticket = create_ticket(summary=message[:200], category=category, priority=priority)
        return {"tool_name": "create_ticket", "tool_output": ticket.model_dump()}

    return {"tool_name": None, "tool_output": None}


def draft_resolution_node(state: AgentState) -> AgentState:
    # Injection attempt: respond with a fixed safe message; never act on the original text.
    if state.get("injection_detected"):
        citation = _best_policy_clause(state)
        cite = f"{citation['source']} {citation['clause']}"
        response = (
            "Your message was flagged as a potential prompt-injection attempt and has been blocked. "
            "Please resubmit your support request without instruction-override language. "
            f"Policy citation: {cite}."
        )
        return {"response": response, "confidence": 0.99}

    citation = _best_policy_clause(state)
    intent = state["intent"]
    tool_output = state.get("tool_output")
    order_id = state.get("order_id")
    amount = state.get("requested_credit_amount")

    cite = f"{citation['source']} {citation['clause']}"
    confidence = 0.78

    if state.get("gate_status") == "escalate":
        ticket_id = (tool_output or {}).get("ticket_id")
        reason = state.get("gate_reason")
        reason_text = {
            "legal_or_threat_language": "your message includes legal or threat language",
            "account_closure_requires_human": "account closure changes account status",
            "credit_over_goodwill_cap": "the requested refund or credit is above the $10 goodwill cap",
        }.get(reason, "this request needs human review")
        response = (
            f"A human support specialist will follow up because {reason_text}. "
            f"I created high-priority ticket {ticket_id}. Policy citation: {cite}."
        )
        return {"response": response, "confidence": 0.98}

    if intent == "out_of_scope":
        response = (
            "I can help with order, billing, delivery, return, account-security, and escalation issues. "
            "I cannot compare competitors or recommend another company. If you have a support issue with an order, "
            f"send the order ID and I can help. Policy citation: {cite}."
        )
        return {"response": response, "confidence": 0.94}

    if intent == "complaint_or_legal":
        ticket_id = (tool_output or {}).get("ticket_id")
        response = (
            "I am escalating this to a human specialist because your message contains legal or formal complaint language. "
            f"Ticket: {ticket_id}. Policy citation: {cite}."
        )
        return {"response": response, "confidence": 0.98}

    if intent == "late_delivery_credit" and isinstance(tool_output, dict):
        credit = tool_output.get("apply_credit")
        if credit:
            response = (
                f"I found order {order_id} and applied a ${credit['amount']:.2f} goodwill credit for the delay. "
                f"Carrier: {tool_output['order_lookup'].get('carrier')}; ETA/delivery date: "
                f"{tool_output['order_lookup'].get('eta')}. Policy citation: {cite}."
            )
            return {"response": response, "confidence": 0.91}
        ticket = tool_output.get("create_ticket")
        if ticket:
            response = (
                f"The requested credit amount ${amount:.2f} is above the $10 goodwill cap, so I created "
                f"ticket {ticket['ticket_id']} for human approval. Policy citation: {cite}."
            )
            return {"response": response, "confidence": 0.96}

    if intent in {"order_status", "cancelled_order"} and isinstance(tool_output, dict):
        if tool_output.get("ok"):
            response = (
                f"Order {tool_output['order_id']} is {tool_output['status']}. Carrier: "
                f"{tool_output.get('carrier') or 'not assigned'}; ETA/delivery date: "
                f"{tool_output.get('eta') or 'not available'}. Policy citation: {cite}."
            )
            return {"response": response, "confidence": 0.89}
        response = f"I could not find that order ID. Please check it and resend. Policy citation: {cite}."
        return {"response": response, "confidence": 0.72}

    if tool_output and "ticket_id" in tool_output:
        response = (
            f"I created ticket {tool_output['ticket_id']} so a support specialist can review this. "
            f"Policy citation: {cite}."
        )
        confidence = 0.84
    else:
        response = (
            "I can help, but I need an order ID or a clearer support issue before taking action. "
            f"Policy citation: {cite}."
        )
        confidence = 0.66

    return {"response": response, "confidence": confidence}


def decide_auto_send_or_escalate_node(state: AgentState) -> AgentState:
    intent = state["intent"]
    confidence = state.get("confidence", 0.0)
    amount = state.get("requested_credit_amount")

    if state.get("injection_detected"):
        decision = "refuse"
    elif state.get("gate_status") == "escalate":
        decision = "escalate"
    elif intent == "out_of_scope":
        decision = "refuse"
    elif state.get("contains_legal_or_threat"):
        decision = "escalate"
    elif amount is not None and amount > GOODWILL_CREDIT_CAP:
        decision = "escalate"
    elif confidence >= 0.8:
        decision = "auto_send"
    else:
        decision = "escalate"

    write_audit_event(
        {
            "event": "agent_decision",
            "intent": intent,
            "confidence": confidence,
            "decision": decision,
            "tool": state.get("tool_name"),
            "injection_detected": state.get("injection_detected", False),
        }
    )
    return {"decision": decision}


# ── Stretch goal nodes (additive — do not modify existing nodes) ─────────

def translate_incoming_node(state: AgentState) -> AgentState:
    """
    Node 0 (before injection screen): detect language, translate to English.
    Guardrails run on the English text, not the original.
    """
    result = process_incoming(state["message"])
    updates: AgentState = {
        "detected_language":     result["detected_language"],
        "translated_to_english": result["translated_to_english"],
        "original_message":      result["original_message"],
    }
    if result["translated_to_english"]:
        updates["message"] = result["english_message"]
    return updates


def sentiment_analysis_node(state: AgentState) -> AgentState:
    """
    Node after classify_intent: score sentiment and flag priority boosts.
    Runs on the (possibly translated) English message.
    """
    result = analyse_sentiment(
        message      = state["message"],
        intent       = state.get("intent", "general_support"),
        contains_legal = state.get("contains_legal_or_threat", False),
    )
    return {
        "sentiment":       result["sentiment"],
        "sentiment_score": result["sentiment_score"],
        "priority_boost":  result["priority_boost"],
    }


def second_opinion_node(state: AgentState) -> AgentState:
    """
    Node after decide_auto_send_or_escalate: re-evaluate borderline decisions.
    Only fires when 0.70 ≤ confidence < 0.90 and no hard governance rule fired.
    May override decision from auto_send → escalate if issues found.
    """
    result = second_opinion(
        message        = state.get("message", ""),
        intent         = state.get("intent", ""),
        confidence     = state.get("confidence", 0.0),
        response       = state.get("response", ""),
        decision       = state.get("decision", "escalate"),
        gate_status    = state.get("gate_status"),
        injection      = state.get("injection_detected", False),
        contains_legal = state.get("contains_legal_or_threat", False),
        tool_name      = state.get("tool_name"),
        priority_boost = state.get("priority_boost", False),
    )
    updates: AgentState = {
        "second_opinion_verdict": result["verdict"],
        "second_opinion_reason":  result["reason"],
    }
    # Only override if verdict calls for it
    if result["verdict"] == "override_to_escalate":
        updates["decision"] = "escalate"
    return updates


def translate_response_node(state: AgentState) -> AgentState:
    """
    Final node: translate the English response back to the customer's language.
    No-op if language is English or translator unavailable.
    """
    lang = state.get("detected_language", "en")
    if lang and lang != "en" and state.get("translated_to_english"):
        translated = translate_response(state.get("response", ""), lang)
        return {"response": translated}
    return {}


def build_graph():
    graph = StateGraph(AgentState)
    # ── Existing nodes ───────────────────────────────────────────────────
    graph.add_node("screen_for_injection",       screen_for_injection_node)
    graph.add_node("classify_intent",            classify_intent_node)
    graph.add_node("retrieve_policy_context",    retrieve_policy_context_node)
    graph.add_node("gate_sensitive_action",      gate_sensitive_action_node)
    graph.add_node("call_relevant_tool",         call_relevant_tool_node)
    graph.add_node("draft_resolution",           draft_resolution_node)
    graph.add_node("decide_auto_send_or_escalate", decide_auto_send_or_escalate_node)
    # ── Stretch nodes ────────────────────────────────────────────────────
    graph.add_node("translate_incoming",  translate_incoming_node)
    graph.add_node("sentiment_analysis",  sentiment_analysis_node)
    graph.add_node("second_opinion",      second_opinion_node)
    graph.add_node("translate_response",  translate_response_node)

    # ── Edges ────────────────────────────────────────────────────────────
    # translate_incoming sits BEFORE injection screen so guardrails run on English
    graph.set_entry_point("translate_incoming")
    graph.add_edge("translate_incoming",            "screen_for_injection")
    graph.add_edge("screen_for_injection",          "classify_intent")
    # sentiment runs immediately after intent is known
    graph.add_edge("classify_intent",               "sentiment_analysis")
    graph.add_edge("sentiment_analysis",            "retrieve_policy_context")
    graph.add_edge("retrieve_policy_context",       "gate_sensitive_action")
    graph.add_edge("gate_sensitive_action",         "call_relevant_tool")
    graph.add_edge("call_relevant_tool",            "draft_resolution")
    graph.add_edge("draft_resolution",              "decide_auto_send_or_escalate")
    # second opinion runs after primary decision, before final response
    graph.add_edge("decide_auto_send_or_escalate",  "second_opinion")
    # translate response back to customer's language last
    graph.add_edge("second_opinion",                "translate_response")
    graph.add_edge("translate_response",            END)
    return graph.compile()


agent_graph = build_graph()


def run_agent_state(message: str) -> AgentState:
    return agent_graph.invoke({"message": message})


def run_agent(message: str) -> str:
    state = run_agent_state(message)
    decision = state.get("decision", "escalate")
    response = state.get("response", "")
    return f"{response}\n\nDecision: {decision}. Confidence: {state.get('confidence', 0.0):.2f}"
