"""
governance/ — AI Governance & Security module for the BVRITH FAQ Chatbot.

Submodules:
    giskard_scan       — Giskard vulnerability scanning (run_giskard_scan)
    security           — Input validation, PII masking, injection detection (SecurityMiddleware)
    promptfoo_bridge   — Promptfoo provider bridge (answer)

Usage:
    from governance.security import SecurityMiddleware
    from governance.giskard_scan import run_giskard_scan
    from governance.promptfoo_bridge import answer as promptfoo_answer
"""

from governance.security import SecurityMiddleware, log_governance_event
from governance.giskard_scan import run_giskard_scan, answer as giskard_answer
from governance.promptfoo_bridge import answer as promptfoo_answer

__all__ = [
    "SecurityMiddleware",
    "log_governance_event",
    "run_giskard_scan",
    "giskard_answer",
    "promptfoo_answer",
]
