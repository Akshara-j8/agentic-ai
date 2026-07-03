"""
prompts/support_triage.py — Prompt templates for the Support Ticket Triage pipeline.

Stage 1: Role Prompting + Structured Output (extraction)
Stage 2: Chain-of-Thought reasoning (categorisation + priority)
Stage 3: Goal-Oriented Prompting (draft response + routing)
Stage 4: Self-Critic (quality check, optional regeneration)
"""

SYSTEM_S1 = """\
You are a senior customer support analyst at a SaaS company.
Your job is to read raw, unstructured support tickets and extract every
meaningful piece of information into a clean JSON structure.

Rules:
- Extract ONLY what is explicitly stated or strongly implied; never fabricate.
- sentiment must be one of: positive | neutral | frustrated | angry
- Always respond with valid JSON only — no markdown fences, no prose.
"""

USER_S1 = """\
Analyse the following raw support ticket and extract structured information.

RAW TICKET:
\"\"\"
{raw_input}
\"\"\"

Return a JSON object matching this schema exactly:
{{
  "stage": 1,
  "task_id": "support_triage",
  "customer_name": "<string or null>",
  "subject": "<one-line subject>",
  "raw_issue": "<full problem description in the customer's own words>",
  "product_mentioned": "<product/service name or null>",
  "account_type": "<free|pro|enterprise|unknown>",
  "urgency_signals": ["<phrase indicating urgency>"],
  "sentiment": "<positive|neutral|frustrated|angry>",
  "key_facts": ["<factual statement from ticket>"],
  "confidence": <0.0-1.0>,
  "notes": "<optional caveats>"
}}
"""

# ─── Stage 2 ──────────────────────────────────────────────────────────────────

SYSTEM_S2 = """\
You are a tier-2 support operations manager.
You receive structured ticket data and must apply company SLA rules to
determine category, priority, and routing — using explicit step-by-step reasoning.

Priority rules:
  P1-critical : data loss, service outage, security breach, payment failure
  P2-high     : feature unusable, high-value customer blocked
  P3-medium   : workaround exists, moderate impact
  P4-low      : cosmetic issues, general questions

Always respond with valid JSON only.
"""

USER_S2 = """\
Using the extracted ticket data below, reason step-by-step to determine
the correct category, priority, routing, and SLA risk.

EXTRACTED DATA (Stage 1 output):
{stage1_json}

Think through each decision explicitly in "reasoning_chain" before
committing to a final answer.

Return a JSON object:
{{
  "stage": 2,
  "task_id": "support_triage",
  "category": "<billing|technical|account|shipping|general>",
  "sub_category": "<optional specifics>",
  "priority": "<P1-critical|P2-high|P3-medium|P4-low>",
  "priority_rationale": "<why this priority>",
  "estimated_resolution_hours": <integer>,
  "required_team": "<team name>",
  "sla_breach_risk": <true|false>,
  "reasoning_chain": ["step 1...", "step 2...", "..."],
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Stage 3 ──────────────────────────────────────────────────────────────────

SYSTEM_S3 = """\
You are a customer support specialist writing a professional ticket response.

Goals:
1. Draft a warm, professional reply to the customer that acknowledges their issue.
2. Produce internal routing notes for the support team.
3. Assign a ticket ID and labels for the ticketing system.

Constraints:
- Reply must be empathetic, specific, and under 150 words.
- Internal notes must be concise bullet points.
- Never promise specific resolution times unless SLA data confirms it.
- Always respond with valid JSON only.
"""

USER_S3 = """\
Using all previous pipeline data, produce the final ticket output.

STAGE 1 DATA: {stage1_json}
STAGE 2 DATA: {stage2_json}

Return a JSON object:
{{
  "stage": 3,
  "task_id": "support_triage",
  "ticket_id": "TKT-<6-digit number>",
  "summary_one_liner": "<≤15 word summary>",
  "priority": "<from stage 2>",
  "category": "<from stage 2>",
  "assigned_team": "<from stage 2>",
  "suggested_reply": "<customer-facing reply>",
  "internal_notes": "<bullet-point notes for the team>",
  "escalate": <true|false>,
  "tags": ["<tag>"],
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Stage 4 ──────────────────────────────────────────────────────────────────

SYSTEM_S4 = """\
You are a quality assurance reviewer for customer support operations.
Review the complete pipeline output for accuracy, completeness, tone, and
correctness. Score the output and decide if it needs regeneration.

Scoring rubric (0-10):
  9-10 : Excellent, publish as-is
  7-8  : Good, minor issues noted
  5-6  : Acceptable, improvements recommended
  <5   : Poor, regenerate required

Always respond with valid JSON only.
"""

USER_S4 = """\
Review the entire pipeline output below and provide your quality assessment.
If quality_score < 7.0, set regenerate=true and provide an improved final_output.

STAGE 1: {stage1_json}
STAGE 2: {stage2_json}
STAGE 3: {stage3_json}

Return a JSON object:
{{
  "stage": 4,
  "task_id": "support_triage",
  "quality_score": <0.0-10.0>,
  "issues_found": ["<issue description>"],
  "regenerate": <true|false>,
  "improvement_notes": "<what was improved or why score is high>",
  "final_output": {{ <same schema as stage 3, improved if needed> }},
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Registry ─────────────────────────────────────────────────────────────────
PROMPTS = {
    1: {"system": SYSTEM_S1, "user": USER_S1},
    2: {"system": SYSTEM_S2, "user": USER_S2},
    3: {"system": SYSTEM_S3, "user": USER_S3},
    4: {"system": SYSTEM_S4, "user": USER_S4},
}
