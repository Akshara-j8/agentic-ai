from agent.graph import run_agent_state


def assert_policy_citation(response: str) -> None:
    assert "Policy citation:" in response, response
    assert ".md " in response, response


def main() -> None:
    status = run_agent_state("Where is order ORD-2002?")
    assert status["intent"] == "order_status"
    assert status["tool_name"] == "order_lookup"
    assert status["decision"] == "auto_send"
    assert_policy_citation(status["response"])

    allowed_credit = run_agent_state("Order ORD-2002 was late, please give me 10 dollars credit")
    assert allowed_credit["tool_name"] == "order_lookup+apply_credit"
    assert allowed_credit["decision"] == "auto_send"
    assert_policy_citation(allowed_credit["response"])

    over_cap = run_agent_state("Order ORD-2002 was late, please give me 25 dollars credit")
    assert over_cap["tool_name"] == "create_ticket"
    assert over_cap["decision"] == "escalate"
    assert "above the $10 goodwill cap" in over_cap["response"]
    assert_policy_citation(over_cap["response"])

    legal = run_agent_state("I will sue you unless you credit ORD-2002 10 dollars")
    assert legal["tool_name"] == "create_ticket"
    assert legal["decision"] == "escalate"
    assert "apply_credit" not in str(legal.get("tool_output"))
    assert_policy_citation(legal["response"])

    out_of_scope = run_agent_state("Which competitor is better than you?")
    assert out_of_scope["intent"] == "out_of_scope"
    assert out_of_scope["decision"] == "refuse"
    assert "cannot compare competitors" in out_of_scope["response"]
    assert_policy_citation(out_of_scope["response"])

    print("Agent guardrail smoke test passed")


if __name__ == "__main__":
    main()
