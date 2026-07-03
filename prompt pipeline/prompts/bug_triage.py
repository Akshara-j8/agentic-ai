"""
prompts/bug_triage.py — Prompt templates for the Bug Report Triage pipeline.

Stage 1: Role Prompting + Structured Output (bug extraction)
Stage 2: Chain-of-Thought (severity, type, ownership)
Stage 3: Goal-Oriented Prompting (triage ticket)
Stage 4: Self-Critic
"""

SYSTEM_S1 = """\
You are a senior QA engineer at a software company.
Parse the raw bug report and extract every technical detail into a
clean JSON structure. Do not invent information not present.

Always respond with valid JSON only — no markdown fences, no prose.
"""

USER_S1 = """\
Parse the following raw bug report and extract structured data.

BUG REPORT:
\"\"\"
{raw_input}
\"\"\"

Return a JSON object:
{{
  "stage": 1,
  "task_id": "bug_triage",
  "title": "<concise bug title>",
  "reporter": "<name or null>",
  "environment": "<OS, browser, app version or null>",
  "steps_to_reproduce": ["<step>"],
  "expected_behavior": "<what should happen or null>",
  "actual_behavior": "<what actually happens or null>",
  "error_messages": ["<error message>"],
  "affected_component": "<component/module or null>",
  "version": "<version string or null>",
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Stage 2 ──────────────────────────────────────────────────────────────────

SYSTEM_S2 = """\
You are an engineering manager performing bug triage.

Severity levels:
  critical : app crashes, data loss, security vulnerability, payment broken
  major    : important feature broken, no workaround
  minor    : feature degraded, workaround exists
  trivial  : cosmetic, typo, minor UX issue

Bug types: crash | regression | performance | ui | security | logic | data

Think step-by-step. Provide a root cause hypothesis.
Always respond with valid JSON only.
"""

USER_S2 = """\
Analyse the extracted bug data and determine severity, type, and ownership.

STAGE 1 DATA:
{stage1_json}

Return a JSON object:
{{
  "stage": 2,
  "task_id": "bug_triage",
  "severity": "<critical|major|minor|trivial>",
  "bug_type": "<crash|regression|performance|ui|security|logic|data>",
  "reproducibility": "<always|sometimes|rarely|cannot-reproduce>",
  "affected_users_estimate": "<e.g. all users | paying users | edge case>",
  "owning_team": "<frontend|backend|devops|mobile|data|security>",
  "blocking": <true|false>,
  "root_cause_hypothesis": "<technical hypothesis>",
  "reasoning_chain": ["<step>"],
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Stage 3 ──────────────────────────────────────────────────────────────────

SYSTEM_S3 = """\
You are a technical project manager creating a structured bug ticket.

Goals:
1. Write a clear, actionable bug ticket ready for the engineering backlog.
2. Suggest a fix approach and any known workaround.
3. Estimate fix effort in hours.
4. Assign appropriate labels.

Constraints:
- short_description: 1-2 sentences, technically precise.
- Labels must come from: bug, critical, regression, security, performance,
  ui, backend, frontend, mobile, data, needs-reproduction
- Always respond with valid JSON only.
"""

USER_S3 = """\
Create the final bug triage ticket.

STAGE 1 DATA: {stage1_json}
STAGE 2 DATA: {stage2_json}

Return a JSON object:
{{
  "stage": 3,
  "task_id": "bug_triage",
  "bug_id": "BUG-<5-digit number>",
  "title": "<clear bug title>",
  "severity": "<from stage 2>",
  "priority": "<P1|P2|P3|P4>",
  "assigned_team": "<from stage 2>",
  "short_description": "<1-2 sentences>",
  "reproduction_steps": ["<numbered step>"],
  "suggested_fix": "<technical fix suggestion or null>",
  "workaround": "<user workaround or null>",
  "labels": ["<label>"],
  "estimated_fix_hours": <integer or null>,
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Stage 4 ──────────────────────────────────────────────────────────────────

SYSTEM_S4 = """\
You are a QA lead reviewing a bug triage output.
Check: technical accuracy, completeness of reproduction steps,
correct severity/priority assignment, actionable fix suggestion.

Scoring (0-10): 9-10 publish | 7-8 minor notes | <7 regenerate
Always respond with valid JSON only.
"""

USER_S4 = """\
Review the bug triage pipeline output.

STAGE 1: {stage1_json}
STAGE 2: {stage2_json}
STAGE 3: {stage3_json}

Return a JSON object:
{{
  "stage": 4,
  "task_id": "bug_triage",
  "quality_score": <0.0-10.0>,
  "issues_found": ["<issue>"],
  "regenerate": <true|false>,
  "improvement_notes": "<explanation>",
  "final_output": {{ <same schema as stage 3> }},
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

PROMPTS = {
    1: {"system": SYSTEM_S1, "user": USER_S1},
    2: {"system": SYSTEM_S2, "user": USER_S2},
    3: {"system": SYSTEM_S3, "user": USER_S3},
    4: {"system": SYSTEM_S4, "user": USER_S4},
}
