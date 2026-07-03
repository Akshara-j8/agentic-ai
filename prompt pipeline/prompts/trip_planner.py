"""
prompts/trip_planner.py — Prompt templates for the Trip Planner pipeline.

Stage 1: Role Prompting + Structured Output (trip request extraction)
Stage 2: Chain-of-Thought (logistics + attraction prioritisation)
Stage 3: Goal-Oriented Prompting (full day-by-day itinerary)
Stage 4: Self-Critic
"""

SYSTEM_S1 = """\
You are a professional travel consultant.
Parse the trip request and extract every meaningful detail.
If budget is not specified, infer budget_level from context (budget|mid-range|luxury).
If duration is not specified, infer a reasonable default from the request.

Always respond with valid JSON only — no markdown fences, no prose.
"""

USER_S1 = """\
Parse the following trip planning request.

REQUEST:
\"\"\"
{raw_input}
\"\"\"

Return a JSON object:
{{
  "stage": 1,
  "task_id": "trip_planner",
  "destination": "<main destination>",
  "origin": "<departure city or null>",
  "travel_dates": "<date range or null>",
  "duration_days": <integer or null>,
  "num_travelers": <integer or null>,
  "budget_usd": <float or null>,
  "budget_level": "<budget|mid-range|luxury>",
  "interests": ["<interest>"],
  "dietary_preferences": ["<preference>"],
  "mobility_requirements": "<note or null>",
  "must_see": ["<attraction or experience>"],
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Stage 2 ──────────────────────────────────────────────────────────────────

SYSTEM_S2 = """\
You are a destination expert and trip logistics planner.

Your job:
1. Recommend the best neighbourhoods to stay in based on interests and budget.
2. List transportation options with rough cost guidance.
3. Curate the top attractions matching the traveller's interests.
4. Flag anything that must be booked in advance.
5. Create a rough budget breakdown across accommodation, food, transport, activities.
6. Provide insider local tips.

Think step-by-step. Always respond with valid JSON only.
"""

USER_S2 = """\
Plan the logistics for this trip.

STAGE 1 DATA:
{stage1_json}

Return a JSON object:
{{
  "stage": 2,
  "task_id": "trip_planner",
  "recommended_neighbourhoods": ["<neighbourhood + why>"],
  "transportation_options": ["<option + approximate cost>"],
  "top_attractions": ["<attraction + brief why>"],
  "must_book_in_advance": ["<item>"],
  "budget_breakdown": {{
    "accommodation_per_night_usd": <float>,
    "food_per_day_usd": <float>,
    "transport_total_usd": <float>,
    "activities_total_usd": <float>
  }},
  "best_time_to_visit": "<season/month recommendation>",
  "local_tips": ["<tip>"],
  "reasoning_chain": ["<step>"],
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Stage 3 ──────────────────────────────────────────────────────────────────

SYSTEM_S3 = """\
You are a luxury travel writer creating a day-by-day itinerary.

Goals:
1. Create a themed day-by-day itinerary with morning, afternoon, evening slots.
2. Include meal recommendations for each day.
3. Provide practical info (currency, visa, emergency contacts, etc.).
4. Suggest a packing list tailored to the destination.
5. Give a total estimated cost.

Constraints:
- Every day must have a theme (e.g., "Culture & History Day").
- Meals should be specific restaurants or food types.
- Practical info keys: currency, language, timezone, visa, emergency
- Always respond with valid JSON only.
"""

USER_S3 = """\
Create the complete day-by-day trip itinerary.

STAGE 1 DATA: {stage1_json}
STAGE 2 DATA: {stage2_json}

Return a JSON object:
{{
  "stage": 3,
  "task_id": "trip_planner",
  "trip_title": "<catchy trip title>",
  "destination": "<destination>",
  "duration_days": <integer>,
  "total_estimated_cost_usd": <float or null>,
  "overview": "<2-3 sentence trip overview>",
  "itinerary": [
    {{
      "day": <integer>,
      "date": "<date or null>",
      "theme": "<day theme>",
      "morning": "<morning activity>",
      "afternoon": "<afternoon activity>",
      "evening": "<evening activity>",
      "meals": ["<breakfast>", "<lunch>", "<dinner>"],
      "estimated_cost_usd": <float or null>
    }}
  ],
  "packing_essentials": ["<item>"],
  "practical_info": {{
    "currency": "<>",
    "language": "<>",
    "timezone": "<>",
    "visa": "<>",
    "emergency": "<>"
  }},
  "emergency_contacts": ["<contact>"],
  "confidence": <0.0-1.0>,
  "notes": "<optional>"
}}
"""

# ─── Stage 4 ──────────────────────────────────────────────────────────────────

SYSTEM_S4 = """\
You are a senior travel editor reviewing a trip itinerary before publication.
Check: destination accuracy, budget realism, itinerary pace (not over-packed),
correct dietary/mobility accommodations, practical info accuracy.

Scoring (0-10): 9-10 publish | 7-8 minor notes | <7 regenerate
Always respond with valid JSON only.
"""

USER_S4 = """\
Review the trip planning pipeline output.

STAGE 1: {stage1_json}
STAGE 2: {stage2_json}
STAGE 3: {stage3_json}

Return a JSON object:
{{
  "stage": 4,
  "task_id": "trip_planner",
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
