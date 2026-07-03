"""
utils/sample_inputs.py — Sample test cases for all 6 pipeline tasks.

Includes 3 real-world examples per task and 1 intentionally broken input
per task to demonstrate graceful error handling.
"""

from __future__ import annotations

SAMPLES: dict[str, list[dict]] = {

    # ─────────────────────────────────────────────────────────────────────────
    "support_triage": [
        {
            "label": "✅ Sample 1 — Billing Issue (High Priority)",
            "input": (
                "Subject: Charged twice for my subscription!!!\n\n"
                "Hi, I noticed that my credit card was charged TWICE this month "
                "for the Pro plan ($49 each). My account is john.doe@example.com. "
                "This is completely unacceptable. I need a refund IMMEDIATELY. "
                "I've been a loyal customer for 3 years and this has never happened before. "
                "Please fix this today or I'm cancelling my account."
            ),
        },
        {
            "label": "✅ Sample 2 — Technical Outage (Critical)",
            "input": (
                "From: Sarah K. (Enterprise Account)\n"
                "Our entire team of 40 engineers cannot log into the platform since 9 AM today. "
                "We get 'Error 503 Service Unavailable' on every page. "
                "We have a major product demo at 2 PM and this is blocking us completely. "
                "We are on the Enterprise plan. Is there a known outage? "
                "Please escalate immediately — our CEO is watching."
            ),
        },
        {
            "label": "✅ Sample 3 — General Inquiry (Low Priority)",
            "input": (
                "Hello, I was wondering if your software supports dark mode? "
                "Also does it work on iPad? I'm thinking about upgrading from the free plan "
                "but wanted to check these things first. Thanks!"
            ),
        },
        {
            "label": "💥 Broken Input — Gibberish (Graceful Handling Demo)",
            "input": "asdfjkl; ??? ### ... ok bye lol 👍👍👍",
        },
    ],

    # ─────────────────────────────────────────────────────────────────────────
    "essay_grader": [
        {
            "label": "✅ Sample 1 — College-Level Essay on Climate Change",
            "input": (
                "The Silent Crisis: Why Climate Change Demands Immediate Action\n\n"
                "Climate change represents the most urgent existential challenge of the twenty-first century. "
                "Despite overwhelming scientific consensus—97% of climate scientists agree on human causation—"
                "political inaction has allowed carbon emissions to reach record levels. "
                "This essay argues that immediate, coordinated international policy action is the only viable path "
                "to preventing catastrophic warming above 1.5 degrees Celsius.\n\n"
                "The Intergovernmental Panel on Climate Change (IPCC) has documented that global temperatures "
                "have already risen 1.1°C above pre-industrial levels. At current trajectories, "
                "we face a 3-4°C rise by 2100, triggering mass extinctions, coastal flooding affecting "
                "600 million people, and food insecurity for billions.\n\n"
                "Critics argue that economic costs of rapid decarbonization are prohibitive. "
                "However, recent analyses by the New Climate Economy project demonstrate that "
                "green investments generate $26 trillion in economic benefits through 2030. "
                "The false choice between economy and environment is a manufactured dilemma.\n\n"
                "Individual action, while meaningful, cannot substitute for systemic change. "
                "Consumer choices matter, but 71% of global emissions come from just 100 companies. "
                "Carbon pricing, renewable energy mandates, and international agreements like the Paris Accord "
                "are the levers that produce meaningful scale.\n\n"
                "The time for half-measures has passed. Governments, corporations, and individuals must act "
                "now with the urgency this crisis demands. Our generation's legacy will be defined by whether "
                "we rose to this challenge or looked away."
            ),
        },
        {
            "label": "✅ Sample 2 — High School Essay (Needs Improvement)",
            "input": (
                "My Favorite Animal\n\n"
                "My favorite animal is dogs. Dogs are very nice and they like to play. "
                "I have a dog named Max. He is a golden retriever and he is 3 years old. "
                "Dogs make good pets because they are loyal and fun. "
                "Some people have cats but I think dogs are better than cats. "
                "Dogs protect your house and bark at strangers. "
                "In conclusion dogs are the best animals and everyone should have one. "
                "They are mans best friend because they are always happy to see you."
            ),
        },
        {
            "label": "✅ Sample 3 — Graduate-Level Analytical Essay",
            "input": (
                "Deconstructing Algorithmic Bias in Machine Learning Systems\n\n"
                "The proliferation of machine learning systems in consequential decision-making domains—"
                "criminal sentencing, credit scoring, medical diagnosis—demands rigorous examination of "
                "how historical inequities become encoded into algorithmic outputs. "
                "This analysis examines the mechanisms by which training data bias propagates through "
                "model architectures, amplifying structural discrimination under the veneer of mathematical objectivity.\n\n"
                "Mehrabi et al. (2021) identify six distinct bias categories: historical, representation, "
                "measurement, aggregation, evaluation, and deployment bias. "
                "Of these, historical bias proves most pernicious because it reflects societal inequities "
                "that existed before any dataset was constructed. A recidivism prediction model trained on "
                "arrest records inherits the racial disparities of a criminal justice system that disproportionately "
                "arrests Black Americans—producing predictions that appear objective while laundering subjective discrimination.\n\n"
                "Technical debiasing approaches—reweighting, resampling, adversarial training—address symptoms "
                "rather than causes. Fairness-aware machine learning must engage with contested normative questions: "
                "fairness for whom, defined how, optimized at what cost? Equalized odds and demographic parity "
                "are mathematically incompatible in most real-world settings (Chouldechova, 2017).\n\n"
                "This paper advocates for interdisciplinary governance frameworks that combine technical auditing "
                "with sociotechnical impact assessments, mandatory transparency reporting, and meaningful "
                "human oversight in high-stakes applications. Algorithmic accountability is ultimately a political "
                "project, not a purely technical one."
            ),
        },
        {
            "label": "💥 Broken Input — Empty/Too Short (Graceful Handling Demo)",
            "input": "ok",
        },
    ],

    # ─────────────────────────────────────────────────────────────────────────
    "bug_triage": [
        {
            "label": "✅ Sample 1 — Critical Crash Bug",
            "input": (
                "Bug Title: App crashes on checkout with items over $999\n"
                "Reporter: Alex Chen (QA Lead)\n"
                "Environment: iOS 17.2, iPhone 14 Pro, App v3.4.1\n"
                "Severity: Critical\n\n"
                "Steps to Reproduce:\n"
                "1. Add any item priced over $999 to cart\n"
                "2. Proceed to checkout\n"
                "3. Enter valid credit card details\n"
                "4. Tap 'Place Order'\n\n"
                "Expected: Order confirmation screen\n"
                "Actual: App crashes immediately with no error message\n\n"
                "Error Log: NullPointerException at PaymentProcessor.swift:247 - "
                "amount field overflow in integer conversion\n\n"
                "This affects all iOS users making high-value purchases. Confirmed reproducible 100% of the time."
            ),
        },
        {
            "label": "✅ Sample 2 — Performance Regression",
            "input": (
                "After deploying v2.8.0 last Tuesday, the dashboard loading time went from ~1 second to 15-20 seconds. "
                "This affects all users. The timeline query is the suspect — it was refactored in this release. "
                "DB query logs show the timeline endpoint making 450+ sequential queries (N+1 problem). "
                "Browser: Chrome 120, Environment: production, Reported by: 47 users in support chat. "
                "Workaround: none. Business impact: high — our SLA requires sub-3s load times."
            ),
        },
        {
            "label": "✅ Sample 3 — UI Bug (Low Priority)",
            "input": (
                "The tooltip on the 'Export' button overlaps with the dropdown menu "
                "when the screen width is between 768-900px. It looks bad but functionality works fine. "
                "Seen on Chrome and Firefox. iPad screen size. Not mobile, not desktop."
            ),
        },
        {
            "label": "💥 Broken Input — Completely Vague (Graceful Handling Demo)",
            "input": "something is broken please fix it",
        },
    ],

    # ─────────────────────────────────────────────────────────────────────────
    "meeting_notes": [
        {
            "label": "✅ Sample 1 — Sprint Planning Meeting",
            "input": (
                "Sprint Planning — March 15, 2024 | 10:00-11:30 AM\n"
                "Attendees: Sarah (PM), Dev (Tech Lead), Maria (Frontend), James (Backend), Priya (Design)\n\n"
                "1. Sprint Goals\n"
                "We agreed the sprint goal is to ship the new onboarding flow and fix the top 3 P1 bugs.\n"
                "Sarah said the onboarding redesign mockups are approved and ready.\n\n"
                "2. Ticket Assignments\n"
                "Maria will take the onboarding UI tickets — she estimated 3 days.\n"
                "James needs to build the onboarding API endpoints. He flagged a dependency on the auth service refactor which Priya is blocking on.\n"
                "Priya said the auth refactor will be done by Wednesday EOD.\n"
                "Dev will handle the P1 bug fixes — estimated 2 days total.\n\n"
                "3. Blockers\n"
                "James is blocked until Priya finishes auth refactor.\n"
                "We still need design sign-off on the email templates — Sarah to follow up with design team by tomorrow.\n\n"
                "4. Decisions\n"
                "We decided to cut the social login feature from this sprint (too risky, move to next sprint).\n"
                "Sprint duration stays at 2 weeks (ending March 29).\n\n"
                "Next sync: Wednesday March 20 standup"
            ),
        },
        {
            "label": "✅ Sample 2 — Quarterly Business Review",
            "input": (
                "Q1 Business Review Notes\n"
                "Participants: CEO (Linda), CFO (Robert), VP Sales (Tom), VP Engineering (Ana)\n\n"
                "Revenue came in at $2.3M vs $2.1M target — 9.5% above plan. Tom's team closed 3 enterprise deals.\n"
                "Churn increased to 4.2% from 2.8% last quarter. Robert flagged this as a concern.\n"
                "Ana announced the infrastructure migration to AWS is 80% complete, final cutover April 5th.\n"
                "Linda: we need to decide on the Series B timing. Board meeting is April 20. Robert to prepare financial projections by April 10.\n"
                "Tom needs to hire 2 more AEs — job postings live by next Friday. HR to send JDs to Tom for approval.\n"
                "Q2 revenue target: $2.8M. Tom said this is achievable if enterprise pipeline closes.\n"
                "Action: Ana to present infrastructure cost savings report at April 20 board meeting."
            ),
        },
        {
            "label": "✅ Sample 3 — Design Review Meeting",
            "input": (
                "Design Review - Mobile App Redesign\n"
                "Present: Jake (Design), Rosa (Product), Wei (iOS Dev)\n\n"
                "Reviewed 3 new screens: home feed, profile, and settings.\n"
                "Jake presented the new card-based home feed. Rosa loved it. Wei raised concern about "
                "animation performance on older iPhones — Jake to simplify transitions.\n"
                "Profile screen: we agreed to move the edit button to the top right.\n"
                "Settings: still need to add the notification preferences section — Jake to add mockup by end of week.\n"
                "Rosa: need user research results before we finalize the nav bar design. She'll send the research report by Thursday.\n"
                "Handoff to Wei starts Monday if Rosa approves."
            ),
        },
        {
            "label": "💥 Broken Input — No Structure (Graceful Handling Demo)",
            "input": "we talked about stuff and things will happen",
        },
    ],

    # ─────────────────────────────────────────────────────────────────────────
    "recipe_adapter": [
        {
            "label": "✅ Sample 1 — Classic Pasta → Vegan + Gluten-Free",
            "input": (
                "Recipe: Classic Spaghetti Carbonara (Serves 4)\n\n"
                "Ingredients:\n"
                "- 400g spaghetti\n"
                "- 200g pancetta or guanciale, diced\n"
                "- 4 large eggs\n"
                "- 100g Pecorino Romano, grated\n"
                "- 50g Parmesan, grated\n"
                "- 2 cloves garlic\n"
                "- Black pepper\n"
                "- Salt\n\n"
                "Instructions:\n"
                "1. Cook pasta in salted boiling water until al dente.\n"
                "2. Fry pancetta until crispy.\n"
                "3. Whisk eggs with grated cheese.\n"
                "4. Combine hot pasta with pancetta, remove from heat.\n"
                "5. Add egg mixture quickly while tossing to create creamy sauce.\n\n"
                "Dietary Requirements: Make this VEGAN and GLUTEN-FREE. "
                "Also increase to 6 servings."
            ),
        },
        {
            "label": "✅ Sample 2 — Chocolate Cake → Nut-Free + Dairy-Free",
            "input": (
                "Recipe: Flourless Chocolate Almond Cake (8 servings)\n\n"
                "Ingredients:\n"
                "- 200g dark chocolate\n"
                "- 100g unsalted butter\n"
                "- 150g almond flour\n"
                "- 200g sugar\n"
                "- 4 eggs\n"
                "- 60ml heavy cream\n"
                "- 1 tsp vanilla extract\n"
                "- Pinch of salt\n\n"
                "Instructions:\n"
                "1. Melt chocolate and butter together.\n"
                "2. Mix in sugar, then eggs one at a time.\n"
                "3. Fold in almond flour and salt.\n"
                "4. Bake at 160°C for 25-30 minutes.\n\n"
                "Requirements: Make this NUT-FREE and DAIRY-FREE for someone with severe nut allergy. "
                "Keep it gluten-free too."
            ),
        },
        {
            "label": "✅ Sample 3 — Chicken Curry → Vegetarian Low-Sodium",
            "input": (
                "Recipe: Butter Chicken Curry (4 servings)\n\n"
                "Ingredients:\n"
                "- 600g chicken breast, cubed\n"
                "- 400ml canned tomatoes\n"
                "- 200ml heavy cream\n"
                "- 3 tbsp butter\n"
                "- 1 onion, diced\n"
                "- 3 cloves garlic\n"
                "- 1 tsp garam masala\n"
                "- 1 tsp turmeric\n"
                "- 1 tsp salt\n"
                "- 1 tsp cumin\n\n"
                "Requirements: Make VEGETARIAN and LOW-SODIUM (under 500mg per serving). "
                "Keep it dairy-free as well."
            ),
        },
        {
            "label": "💥 Broken Input — No Recipe Provided (Graceful Handling Demo)",
            "input": "make it healthy please thanks",
        },
    ],

    # ─────────────────────────────────────────────────────────────────────────
    "trip_planner": [
        {
            "label": "✅ Sample 1 — Budget Backpacker Trip to Japan",
            "input": (
                "I want to visit Tokyo and Kyoto for 7 days in April 2025. "
                "I'm travelling solo on a budget of $1200 USD total. "
                "I love street food, anime/manga culture, temples, and traditional markets. "
                "I don't have any dietary restrictions. "
                "I want to see Senso-ji temple, Akihabara, and the bamboo forest in Arashiyama."
            ),
        },
        {
            "label": "✅ Sample 2 — Luxury Family Trip to Bali",
            "input": (
                "Planning a luxury family vacation to Bali for 10 days in July. "
                "Party of 4: 2 adults and 2 kids aged 8 and 12. "
                "Budget is around $8000 USD. "
                "We want luxury resorts, family-friendly activities, beaches, some cultural experiences. "
                "One of our kids is vegetarian. We need easy access — no excessive hiking. "
                "Must see: Ubud rice terraces, Tanah Lot temple, and a cooking class."
            ),
        },
        {
            "label": "✅ Sample 3 — Weekend City Break to Paris",
            "input": (
                "Quick 3-day weekend trip to Paris from London. "
                "Couple, mid-range budget around £800. "
                "First time in Paris. Love art, food, and romantic spots. "
                "We want to see the Eiffel Tower, Louvre, and Montmartre. "
                "One of us is lactose intolerant. "
                "Travelling by Eurostar."
            ),
        },
        {
            "label": "💥 Broken Input — Conflicting Requirements (Graceful Handling Demo)",
            "input": "want to go everywhere in 1 day budget is $0 no flying no trains no buses",
        },
    ],
}
