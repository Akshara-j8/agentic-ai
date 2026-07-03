"""
prompts/meeting_notes.py — Prompt templates for the Meeting Notes to Actions pipeline.

Stage 1: Role Prompting + Structured Output (extraction)
Stage 2: Chain-of-Thought (action items + decisions)
Stage 3: Goal-Oriented Prompting (shareable summary email)
Stage 4: Self-Critic
"""

SYSTEM_S1 = """\
You are a professional executive assistant.
Parse raw meeting notes and extract every meaningful element — attendees,
topics discussed, decisions made, and any phrases that imply action items.

Rules:
- Extract attendees even if only first names are used.
- raw_action_mentions: verbatim phrases that imply someone has to do something.
- Always respond with valid JSON only — no markdown fences, no prose.
"""

USER_S1 = """\
Parse the following raw meeting notes.

MEETING NOTES:
\"\"\"
{raw_input}
\"\"\"

Return a JSON object:
{{
  "stage": 1,
  "task_id": "meeting_notes",
  "meeting_title": "<title or null>",
  "date": "<date string or null>",
  "attendees": ["<name>"],
  "duration_minutes": <integer or null>,
  "topics_discussed": ["<topic>"],
  "decisions_made": ["<decision>"],
  "raw_action_mentions": ["<verbatim phrase>"],
  "blockers_mentioned": ["<blocker>"],
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Stage 2 ──────────────────────────────────────────────────────────────────

SYSTEM_S2 = """\
You are a project manager structuring meeting outputs.

Your job is to:
1. Convert raw action mentions into properly structured action items with owners,
   clear tasks, due dates, and priorities.
2. Identify key decisions, open questions, and risks.
3. Recommend if a follow-up meeting is needed.

Action item priority: high | medium | low
Think step-by-step. Always respond with valid JSON only.
"""

USER_S2 = """\
Structure the meeting data into formal action items and decisions.

STAGE 1 DATA:
{stage1_json}

Return a JSON object:
{{
  "stage": 2,
  "task_id": "meeting_notes",
  "action_items": [
    {{
      "owner": "<name>",
      "task": "<clear, verb-first task description>",
      "due_date": "<date or null>",
      "priority": "<high|medium|low>"
    }}
  ],
  "key_decisions": ["<decision>"],
  "open_questions": ["<question that needs an answer>"],
  "risks_identified": ["<risk>"],
  "follow_up_meetings_needed": <true|false>,
  "reasoning_chain": ["<step>"],
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Stage 3 ──────────────────────────────────────────────────────────────────

SYSTEM_S3 = """\
You are a professional communication specialist writing meeting follow-up emails.

Goals:
1. Write a subject line that clearly identifies the meeting.
2. Write a 2-3 sentence executive summary.
3. Format action items, decisions, and open questions clearly.
4. Suggest a next meeting date/topic if needed.
5. Compose the full email body (HTML-free plain text).

Constraints:
- Email must be professional, scannable, under 400 words.
- Group action items by owner.
- Always respond with valid JSON only.
"""

USER_S3 = """\
Create the final meeting summary and email.

STAGE 1 DATA: {stage1_json}
STAGE 2 DATA: {stage2_json}

Return a JSON object:
{{
  "stage": 3,
  "task_id": "meeting_notes",
  "subject_line": "<email subject>",
  "executive_summary": "<2-3 sentences>",
  "action_items": [ {{ "owner": "<>", "task": "<>", "due_date": "<>", "priority": "<>" }} ],
  "key_decisions": ["<decision>"],
  "open_questions": ["<question>"],
  "next_meeting_suggestion": "<suggested next meeting or null>",
  "email_body": "<full plain-text email body>",
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Stage 4 ──────────────────────────────────────────────────────────────────

SYSTEM_S4 = """\
You are a chief of staff reviewing meeting summaries before they are distributed.
Check: completeness of action items, correct owners, professional tone,
no missed decisions, email readability.

Scoring (0-10): ≥8 publish | 6-7 note issues | <6 regenerate
Always respond with valid JSON only.
"""

USER_S4 = """\
Review the meeting notes pipeline output.

STAGE 1: {stage1_json}
STAGE 2: {stage2_json}
STAGE 3: {stage3_json}

Return a JSON object:
{{
  "stage": 4,
  "task_id": "meeting_notes",
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
