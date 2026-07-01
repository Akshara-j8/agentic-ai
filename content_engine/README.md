<<<<<<< HEAD
# AI Content Engine

Generate a complete marketing campaign — tagline, blog intro, social posts, hero image, and promo video — from a single product brief.

---

## Project Structure

```
content_engine/
├── app.py           # Streamlit UI
├── text_gen.py      # Tagline, blog, social posts (OpenRouter)
├── image_gen.py     # Hero image (OpenAI gpt-image-1)
├── video_gen.py     # Promo video (Runway image-to-video)
├── config.py        # Environment variable loader
├── requirements.txt
├── .env.example
└── README.md
```

---

## API Setup

| API | Purpose | Where to get key |
|-----|---------|-----------------|
| OpenRouter | LLM text generation | https://openrouter.ai/keys |
| OpenAI | Image generation (gpt-image-1) | https://platform.openai.com/api-keys |
| Runway | Image-to-video | https://app.runwayml.com/settings/api-keys |

---

## Installation

```bash
# 1. Clone / navigate to project
cd content_engine

# 2. Create and activate virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
RUNWAY_API_KEY=your_runway_api_key_here
```

---

## How to Run

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Usage

1. Enter **Product Name** and **Target Audience** in the sidebar.
2. Select a **Brand Tone** (Premium, Eco, Playful, Minimal, Luxury, Modern).
3. Click **✨ Generate Campaign Suite**.
4. Wait for all 5 steps to complete (~60–90 seconds total).
5. Review and copy your campaign assets.

---

## Generation Pipeline

| Step | Output | API | Technique |
|------|--------|-----|-----------|
| 1 | Campaign Tagline | OpenRouter | Few-shot prompting |
| 2 | Blog Introduction (200 words) | OpenRouter | Role prompting |
| 3 | Social Posts (Twitter/Instagram/LinkedIn) | OpenRouter | Structured JSON output |
| 4 | Hero Image (16:9) | OpenAI gpt-image-1 | Dynamic prompt formula |
| 5 | Promotional Video (8s) | Runway gen4_turbo | Image-to-video |

---

## Screenshots

<!-- Add screenshots here after first run -->
| Sidebar | Left Column | Right Column |
|---------|-------------|--------------|
| _screenshot_ | _screenshot_ | _screenshot_ |

---

## Error Handling

- Every API call retries up to **3 times** with exponential back-off.
- Errors are shown inline via `st.error()` — the app never crashes.
- If video generation fails, all text and image assets are still displayed.
=======
# agentic-ai
>>>>>>> f959e01fd82e5a8af64a2ed6011db2483cca8a4d
