"""Text generation via OpenRouter: tagline, blog intro, social posts."""

import json
import time
from typing import Any

import requests

import config

_HEADERS = {
    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}

_MAX_RETRIES = 3
_RETRY_DELAY = 2  # seconds


def _chat(messages: list[dict], **kwargs) -> str:
    """Send a chat completion request with retry logic."""
    payload = {"model": config.OPENROUTER_MODEL, "messages": messages, **kwargs}
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{config.OPENROUTER_BASE_URL}/chat/completions",
                headers=_HEADERS,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            if attempt == _MAX_RETRIES:
                raise RuntimeError(f"OpenRouter call failed after {_MAX_RETRIES} attempts: {exc}") from exc
            time.sleep(_RETRY_DELAY * attempt)


def generate_tagline(product: str, audience: str, tone: str) -> str:
    """
    Generate a campaign tagline using few-shot prompting.

    Args:
        product: Product name.
        audience: Target audience description.
        tone: Brand tone (e.g. Premium, Eco).

    Returns:
        A short tagline string (max 10 words).
    """
    messages = [
        {
            "role": "user",
            "content": (
                "Generate a campaign tagline. Max 10 words. Memorable. No hashtags. "
                "Match the brand tone. Return plain text only.\n\n"
                "Examples:\n"
                "- Product: AquaPure Water Bottle | Audience: Fitness enthusiasts | Tone: Minimal → Pure Hydration, Simply Delivered.\n"
                "- Product: GreenLeaf Tea | Audience: Health-conscious adults | Tone: Eco → Nature's Best Cup, Sustainably Yours.\n"
                "- Product: LuxeWatch | Audience: Affluent professionals | Tone: Luxury → Time Perfected. Legacy Defined.\n\n"
                f"Product: {product} | Audience: {audience} | Tone: {tone}"
            ),
        }
    ]
    return _chat(messages, max_tokens=30, temperature=0.8)


def generate_blog_intro(product: str, audience: str, tone: str, tagline: str) -> str:
    """
    Generate a 200-word blog introduction using role prompting.

    Args:
        product: Product name.
        audience: Target audience description.
        tone: Brand tone.
        tagline: Campaign tagline from Step 1.

    Returns:
        A ~200-word blog introduction string.
    """
    messages = [
        {
            "role": "system",
            "content": "You are an award-winning content strategist.",
        },
        {
            "role": "user",
            "content": (
                f"Write a blog introduction of exactly 200 words for '{product}'.\n"
                f"Target audience: {audience}\n"
                f"Brand tone: {tone}\n"
                f"Campaign tagline: \"{tagline}\"\n\n"
                "Weave the tagline naturally into the intro. "
                "Match the brand tone throughout. Return only the blog text."
            ),
        },
    ]
    return _chat(messages, max_tokens=350, temperature=0.7)


def generate_social_posts(product: str, audience: str, tone: str, tagline: str) -> dict[str, str]:
    """
    Generate platform-specific social media posts as strict JSON.

    Args:
        product: Product name.
        audience: Target audience description.
        tone: Brand tone.
        tagline: Campaign tagline.

    Returns:
        Dict with keys: twitter, instagram, linkedin.
    """
    messages = [
        {
            "role": "user",
            "content": (
                f"Create social media posts for '{product}'.\n"
                f"Target audience: {audience} | Brand tone: {tone} | Tagline: \"{tagline}\"\n\n"
                "Rules:\n"
                "- Twitter: max 280 characters\n"
                "- Instagram: max 2200 characters\n"
                "- LinkedIn: max 700 characters\n"
                "- Match brand tone. Include relevant emojis where appropriate.\n\n"
                'Return STRICT JSON only — no markdown, no explanation:\n'
                '{"twitter":"","instagram":"","linkedin":""}'
            ),
        }
    ]
    raw = _chat(messages, max_tokens=800, temperature=0.75)
    # Strip possible markdown fences
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Social posts JSON parse failed: {exc}\nRaw: {raw}") from exc
    return {k: data.get(k, "") for k in ("twitter", "instagram", "linkedin")}
