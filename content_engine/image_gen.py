"""Hero image generation via OpenRouter — FLUX 1.0 (black-forest-labs/flux-1)."""

import time
from base64 import b64decode

import requests

import config

_MAX_RETRIES = 3
_RETRY_DELAY = 2

_HEADERS = {
    "Authorization": f"Bearer {config.OPENROUTER_IMAGE_API_KEY}",
    "Content-Type": "application/json",
}

# Tone → style descriptors
_TONE_STYLES: dict[str, str] = {
    "Premium":  "photorealistic, luxury studio lighting, polished surfaces",
    "Eco":      "natural earthy colors, watercolor aesthetic, organic feel",
    "Playful":  "bright vibrant illustration, bold colors, fun energetic style",
    "Minimal":  "white background, minimalist clean composition, modern simplicity",
    "Luxury":   "elegant dark background, gold accents, dramatic cinematic lighting",
    "Modern":   "clean product photography, sharp focus, contemporary lifestyle setting",
}

_CONSTRAINTS = "No text, no watermark, no logo. Ultra detailed."


def build_image_prompt(product: str, audience: str, tone: str, tagline: str) -> str:
    """
    Construct a detailed image generation prompt.

    Args:
        product: Product name.
        audience: Target audience.
        tone: Brand tone key.
        tagline: Campaign tagline for thematic alignment.

    Returns:
        Full prompt string.
    """
    style = _TONE_STYLES.get(tone, _TONE_STYLES["Modern"])
    return (
        f"Hero product marketing image for '{product}'. "
        f"Target audience: {audience}. Campaign tagline: \"{tagline}\". "
        f"Style: {style}. "
        "Composition: centered subject, rule of thirds, ample negative space. "
        "Lighting: soft directional light with subtle shadows. "
        "Camera angle: eye-level slight overhead perspective. "
        f"{_CONSTRAINTS}"
    )


def generate_hero_image(product: str, audience: str, tone: str, tagline: str) -> bytes:
    """
    Generate a hero image using FLUX 1.0 via OpenRouter and return PNG bytes.

    Args:
        product: Product name.
        audience: Target audience.
        tone: Brand tone.
        tagline: Campaign tagline.

    Returns:
        PNG image as bytes.

    Raises:
        RuntimeError: After max retries exhausted.
    """
    prompt = build_image_prompt(product, audience, tone, tagline)
    payload = {
        "model": config.IMAGE_MODEL,
        "prompt": prompt,
        "aspect_ratio": "16:9",
    }

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{config.OPENROUTER_BASE_URL}/images",
                headers=_HEADERS,
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            return b64decode(resp.json()["data"][0]["b64_json"])
        except Exception as exc:
            if attempt == _MAX_RETRIES:
                raise RuntimeError(f"Image generation failed after {_MAX_RETRIES} attempts: {exc}") from exc
            time.sleep(_RETRY_DELAY * attempt)
