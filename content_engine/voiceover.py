"""
Voiceover Generation — converts a blog introduction into a narration-friendly
script (with natural pause markers) and generates a playable MP3 audio file.

Pipeline:
  1. adapt_blog_to_narration() — calls OpenRouter to rewrite the blog text
     into a natural spoken-word script with [PAUSE] markers.
  2. generate_mp3()            — strips the markers, feeds clean text to gTTS,
     and returns raw MP3 bytes ready for st.audio().

No additional API keys required beyond the existing OPENROUTER_API_KEY.
"""

import io
import re
import time

import requests
from gtts import gTTS

import config

_HEADERS = {
    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}

# Pause marker inserted by the LLM, stripped before TTS
_PAUSE_MARKER = "[PAUSE]"


# ── Narration script adaptation ────────────────────────────────────────────────

def adapt_blog_to_narration(
    blog: str,
    product: str,
    audience: str,
    tone: str,
) -> str:
    """
    Use OpenRouter to rewrite the blog introduction as a spoken narration script.

    Transformations applied by the LLM:
    - Converts formal writing to conversational spoken language.
    - Shortens complex sentences for natural breath pacing.
    - Inserts [PAUSE] markers at logical breath / emphasis points.
    - Removes markdown, bullets, and any symbols that do not read aloud well.
    - Keeps total spoken duration to approximately 60–90 seconds (~120-180 words).

    Args:
        blog:     The blog introduction text to convert.
        product:  Product name (for context).
        audience: Target audience (to tune spoken register).
        tone:     Brand tone (to match energy of narration).

    Returns:
        Narration script as a string with [PAUSE] markers embedded.

    Raises:
        RuntimeError: If OpenRouter fails after 3 attempts.
    """
    prompt = (
        "You are a professional voiceover scriptwriter.\n"
        "Rewrite the blog introduction below as a spoken narration script.\n\n"
        "=== RULES ===\n"
        "1. Convert all formal writing to natural conversational speech.\n"
        "2. Break long sentences into short, breathable phrases.\n"
        "3. Insert [PAUSE] at natural breath points — after strong statements, "
        "before topic shifts, and at the end of key phrases. Aim for one [PAUSE] "
        "every 2-3 sentences.\n"
        "4. Remove all markdown formatting, bullet points, asterisks, and symbols "
        "that would sound unnatural when read aloud.\n"
        "5. Keep total word count between 120-180 words for a 60-90 second read.\n"
        "6. Match the brand tone: energetic for Playful/Modern, calm and authoritative "
        "for Premium/Luxury, warm and trustworthy for Eco/Minimal.\n"
        "7. End with a clear call-to-action sentence.\n"
        "8. Return ONLY the narration script — no labels, no explanations.\n\n"
        f"=== CONTEXT ===\n"
        f"Product: {product}\n"
        f"Audience: {audience}\n"
        f"Brand Tone: {tone}\n\n"
        f"=== BLOG INTRODUCTION ===\n{blog}"
    )

    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are a professional voiceover scriptwriter."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 400,
        "temperature": 0.65,
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
                    f"Narration script adaptation failed after 3 attempts: {exc}"
                ) from exc
            time.sleep(2 * attempt)

    # Unreachable, but satisfies type checker
    raise RuntimeError("Narration script adaptation failed.")


# ── MP3 generation ─────────────────────────────────────────────────────────────

def _clean_for_tts(script: str) -> str:
    """
    Remove [PAUSE] markers and any remaining markdown artifacts before TTS.

    gTTS reads text character-by-character, so brackets and special markers
    must be stripped to avoid them being spoken aloud.

    Args:
        script: Narration script with [PAUSE] markers.

    Returns:
        Plain text safe for TTS input.
    """
    # Replace [PAUSE] with a short silent comma-pause (gTTS respects commas)
    text = script.replace(_PAUSE_MARKER, ",")
    # Remove any leftover markdown (bold, italic, headers)
    text = re.sub(r"[*_#`>~]", "", text)
    # Collapse multiple spaces / newlines
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def generate_mp3(narration_script: str, lang: str = "en") -> bytes:
    """
    Convert the narration script to MP3 bytes using gTTS.

    The [PAUSE] markers are converted to comma-pauses so gTTS produces
    natural-sounding pacing without any additional audio processing.

    Args:
        narration_script: Script text with optional [PAUSE] markers.
        lang:             BCP-47 language code (default: 'en').

    Returns:
        Raw MP3 bytes suitable for st.audio() or file download.

    Raises:
        RuntimeError: If gTTS fails to generate audio.
    """
    clean_text = _clean_for_tts(narration_script)
    if not clean_text:
        raise ValueError("Narration script is empty after cleaning — cannot generate audio.")

    try:
        tts = gTTS(text=clean_text, lang=lang, slow=False)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return buffer.read()
    except Exception as exc:
        raise RuntimeError(f"gTTS MP3 generation failed: {exc}") from exc


# ── Combined pipeline ──────────────────────────────────────────────────────────

def generate_voiceover(
    blog: str,
    product: str,
    audience: str,
    tone: str,
) -> tuple[str, bytes]:
    """
    Full voiceover pipeline: adapt blog → generate MP3.

    Args:
        blog:     Blog introduction text.
        product:  Product name.
        audience: Target audience.
        tone:     Brand tone.

    Returns:
        Tuple of (narration_script: str, mp3_bytes: bytes).
        - narration_script includes [PAUSE] markers for display in the UI.
        - mp3_bytes is the raw audio ready for st.audio() or download.

    Raises:
        RuntimeError: On script adaptation or TTS failure.
    """
    narration_script = adapt_blog_to_narration(blog, product, audience, tone)
    mp3_bytes = generate_mp3(narration_script)
    return narration_script, mp3_bytes
