"""
Multi-Channel Adaptation — rewrites text assets (tagline, blog, social posts)
for a specific distribution channel while leaving image and video assets unchanged.

Supported channels:
  - gen_z_tiktok   : Casual, trend-aware, short-form, emoji-heavy Gen-Z voice.
  - b2b_linkedin   : Professional, data-driven, thought-leadership B2B tone.
  - parents_facebook: Warm, reassuring, benefit-focused tone for parents.

All text rewriting is done via OpenRouter using the existing OPENROUTER_API_KEY.
Image and video assets are returned as-is — this module never touches them.
"""

import json
import time
from dataclasses import dataclass

import requests

import config
import text_gen

# ── Channel definitions ────────────────────────────────────────────────────────

CHANNELS: dict[str, str] = {
    "gen_z_tiktok":     "Gen-Z TikTok",
    "b2b_linkedin":     "B2B LinkedIn",
    "parents_facebook": "Parents Facebook",
}

_CHANNEL_PERSONAS: dict[str, str] = {
    "gen_z_tiktok": (
        "You are a Gen-Z TikTok content creator. "
        "Write in a casual, hyper-energetic, trend-aware style. "
        "Use internet slang (e.g. 'no cap', 'lowkey', 'fr fr', 'it's giving', 'slay'), "
        "relevant emojis (every 1-2 sentences), and short punchy sentences. "
        "Avoid corporate language entirely. Make it feel authentic, not forced."
    ),
    "b2b_linkedin": (
        "You are a B2B LinkedIn thought-leader. "
        "Write in a professional, authoritative, data-driven style. "
        "Lead with a bold insight or statistic when possible. "
        "Use clear paragraphs, industry-appropriate vocabulary, and a strategic angle. "
        "Minimal emojis (one or two at most). End with a thought-provoking question or CTA."
    ),
    "parents_facebook": (
        "You are writing for a Facebook community of parents. "
        "Use a warm, reassuring, relatable tone. Focus on safety, family benefits, "
        "and real-life value. Write in plain everyday language — no jargon. "
        "Include a sense of community ('other parents love this', 'your family deserves'). "
        "Use friendly emojis sparingly. Keep sentences conversational and approachable."
    ),
}

_HEADERS = {
    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}


# ── Data types ─────────────────────────────────────────────────────────────────

@dataclass
class AdaptedAssets:
    """Rewritten text assets for a specific channel."""
    channel_key: str       # e.g. "gen_z_tiktok"
    channel_label: str     # e.g. "Gen-Z TikTok"
    tagline: str
    blog: str
    social: dict[str, str]  # keys: twitter, instagram, linkedin


# ── Internal helpers ───────────────────────────────────────────────────────────

def _adapt_text(
    persona: str,
    asset_name: str,
    original: str,
    product: str,
    audience: str,
    tone: str,
    extra_instruction: str = "",
) -> str:
    """
    Rewrite a single text asset for the given channel persona via OpenRouter.

    Args:
        persona:           Channel persona prompt defining the rewrite voice.
        asset_name:        Human label for the asset (used in the prompt).
        original:          Original generated text to rewrite.
        product:           Product name (kept consistent in the rewrite).
        audience:          Original target audience (for reference).
        tone:              Original brand tone (for reference).
        extra_instruction: Any format or length constraints for this asset.

    Returns:
        Rewritten text as a string.

    Raises:
        RuntimeError: After 3 failed attempts.
    """
    prompt = (
        f"Rewrite the following {asset_name} for the channel described below.\n\n"
        f"=== CHANNEL PERSONA ===\n{persona}\n\n"
        f"=== ORIGINAL CONTENT ===\n{original}\n\n"
        f"=== CONSTRAINTS ===\n"
        f"- Keep the product name '{product}' accurate and prominent.\n"
        f"- Preserve the core message and key benefits.\n"
        f"- Do NOT change any facts about the product.\n"
        f"{'- ' + extra_instruction if extra_instruction else ''}\n\n"
        f"Return ONLY the rewritten {asset_name} — no labels, no explanations."
    )

    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 500,
        "temperature": 0.75,
    }

    for attempt in range(1, 4):
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
            if attempt == 3:
                raise RuntimeError(
                    f"Channel adaptation failed for {asset_name} after 3 attempts: {exc}"
                ) from exc
            time.sleep(2 * attempt)

    raise RuntimeError(f"Channel adaptation failed for {asset_name}.")


def _adapt_social_posts(
    persona: str,
    original_social: dict[str, str],
    product: str,
    audience: str,
    tone: str,
    channel_key: str,
) -> dict[str, str]:
    """
    Rewrite all three social posts as a single JSON API call for efficiency.

    Args:
        persona:         Channel persona prompt.
        original_social: Dict with keys 'twitter', 'instagram', 'linkedin'.
        product:         Product name.
        audience:        Target audience.
        tone:            Brand tone.
        channel_key:     Channel key for context.

    Returns:
        Dict with keys 'twitter', 'instagram', 'linkedin' — rewritten posts.
    """
    prompt = (
        f"Rewrite the following social media posts for the channel persona described below.\n\n"
        f"=== CHANNEL PERSONA ===\n{persona}\n\n"
        f"=== ORIGINAL POSTS ===\n"
        f"Twitter: {original_social.get('twitter', '')}\n\n"
        f"Instagram: {original_social.get('instagram', '')}\n\n"
        f"LinkedIn: {original_social.get('linkedin', '')}\n\n"
        f"=== CONSTRAINTS ===\n"
        f"- Keep the product name '{product}' accurate and prominent.\n"
        f"- Twitter: max 280 characters.\n"
        f"- Instagram: max 2200 characters.\n"
        f"- LinkedIn: max 700 characters.\n"
        f"- Adapt tone and vocabulary for the channel persona — not just synonyms.\n"
        f"- Do NOT change any facts about the product.\n\n"
        'Return STRICT JSON only — no markdown, no explanation:\n'
        '{"twitter":"","instagram":"","linkedin":""}'
    )

    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 900,
        "temperature": 0.75,
    }

    for attempt in range(1, 4):
        try:
            resp = requests.post(
                f"{config.OPENROUTER_BASE_URL}/chat/completions",
                headers=_HEADERS,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)
            return {k: data.get(k, original_social.get(k, "")) for k in ("twitter", "instagram", "linkedin")}
        except Exception as exc:
            if attempt == 3:
                # Fall back to original posts rather than crash
                return original_social
            time.sleep(2 * attempt)

    return original_social


# ── Public API ─────────────────────────────────────────────────────────────────

def adapt_for_channel(
    channel_key: str,
    product: str,
    audience: str,
    tone: str,
    tagline: str,
    blog: str,
    social: dict[str, str],
) -> AdaptedAssets:
    """
    Rewrite all text assets for the specified distribution channel.

    Image and video assets are NOT handled here — they are passed through
    unchanged in the calling UI layer.

    Args:
        channel_key: One of 'gen_z_tiktok', 'b2b_linkedin', 'parents_facebook'.
        product:     Product name.
        audience:    Original target audience.
        tone:        Original brand tone.
        tagline:     Original campaign tagline.
        blog:        Original blog introduction.
        social:      Original social posts dict (twitter, instagram, linkedin).

    Returns:
        AdaptedAssets dataclass with rewritten tagline, blog, and social posts.

    Raises:
        ValueError:   If channel_key is not recognised.
        RuntimeError: If any OpenRouter call fails after retries.
    """
    if channel_key not in _CHANNEL_PERSONAS:
        valid = ", ".join(_CHANNEL_PERSONAS.keys())
        raise ValueError(
            f"Unknown channel '{channel_key}'. Valid options: {valid}"
        )

    persona = _CHANNEL_PERSONAS[channel_key]
    channel_label = CHANNELS[channel_key]

    # Adapt tagline (keep it short — max 12 words for adapted versions)
    adapted_tagline = _adapt_text(
        persona=persona,
        asset_name="campaign tagline",
        original=tagline,
        product=product,
        audience=audience,
        tone=tone,
        extra_instruction="Max 12 words. No hashtags. Return plain text only.",
    )

    # Adapt blog introduction
    adapted_blog = _adapt_text(
        persona=persona,
        asset_name="blog introduction",
        original=blog,
        product=product,
        audience=audience,
        tone=tone,
        extra_instruction="Maintain approximately the same length as the original (150-250 words).",
    )

    # Adapt all three social posts in one call
    adapted_social = _adapt_social_posts(
        persona=persona,
        original_social=social,
        product=product,
        audience=audience,
        tone=tone,
        channel_key=channel_key,
    )

    return AdaptedAssets(
        channel_key=channel_key,
        channel_label=channel_label,
        tagline=adapted_tagline,
        blog=adapted_blog,
        social=adapted_social,
    )
