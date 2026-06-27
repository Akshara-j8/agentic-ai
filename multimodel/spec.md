# Spec — Multi-Model Comparison Tool

## Goal
Ask one question to four free LLMs via OpenRouter and show each answer
with its speed and token usage, so I can compare models at zero cost.

## Input
- A single question (string). Hardcoded for now; later read from input.

## Output (per model)
- answer text
- latency (seconds)
- tokens (in / out)

## Models (OpenRouter free tier — no credits needed)
- google/gemma-4-31b-it:free
- openai/gpt-oss-120b:free

## Pipeline
1. Load OPENROUTER_API_KEY from .env.
2. For each model: send the question, time the call, read token usage.
3. Print results for all four models.

## Error handling
- Wrap each model call in try/except; on failure, log it and continue.

## Done when
- One run shows four answers, each with latency and token counts.
- One failing model does not stop the others.
- No API key appears in the code.
- No paid credits are required.
