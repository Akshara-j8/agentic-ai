"""TechVest Recruitment Agent — Tools package."""

from tools.parser import parse_resume, extract_text_from_pdf_bytes
from tools.scorer import score_candidate
from tools.availability import check_availability
from tools.scheduler import propose_interview, confirm_slot_for_candidate
from tools.fairness import fairness_check, prompt_injection_detector, audit_logger_tool

# All LangChain tools registered for agent use
ALL_TOOLS = [
    parse_resume,
    score_candidate,
    check_availability,
    propose_interview,
    fairness_check,
    prompt_injection_detector,
    audit_logger_tool,
]

__all__ = [
    "parse_resume",
    "extract_text_from_pdf_bytes",
    "score_candidate",
    "check_availability",
    "propose_interview",
    "confirm_slot_for_candidate",
    "fairness_check",
    "prompt_injection_detector",
    "audit_logger_tool",
    "ALL_TOOLS",
]
