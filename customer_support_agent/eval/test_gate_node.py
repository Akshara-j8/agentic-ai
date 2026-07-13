import unittest

from agent.graph import run_agent_state


class SensitiveActionGateTests(unittest.TestCase):
    def assert_gate_escalated(self, state: dict) -> None:
        self.assertEqual(state["gate_status"], "escalate")
        self.assertEqual(state["tool_name"], "create_ticket")
        self.assertEqual(state["decision"], "escalate")
        self.assertIn("human support specialist will follow up", state["response"])
        self.assertIn("Policy citation:", state["response"])
        self.assertNotIn("apply_credit", str(state.get("tool_output")))
        self.assertEqual(state["tool_output"]["priority"], "high")

    def test_gate_blocks_credit_over_goodwill_cap(self) -> None:
        state = run_agent_state("Order ORD-2002 was late, please give me 25 dollars credit")
        self.assertEqual(state["gate_reason"], "credit_over_goodwill_cap")
        self.assert_gate_escalated(state)

    def test_gate_blocks_account_closure_request(self) -> None:
        state = run_agent_state("Please close my account after checking order ORD-2001")
        self.assertEqual(state["intent"], "account_closure")
        self.assertEqual(state["gate_reason"], "account_closure_requires_human")
        self.assert_gate_escalated(state)

    def test_gate_blocks_legal_threat_even_under_cap(self) -> None:
        state = run_agent_state("I will sue unless you give ORD-2002 a 10 dollars credit")
        self.assertEqual(state["gate_reason"], "legal_or_threat_language")
        self.assert_gate_escalated(state)


if __name__ == "__main__":
    unittest.main()
