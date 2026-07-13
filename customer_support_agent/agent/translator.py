"""
agent/translator.py
===================
Multilingual support — same guardrails in every language.

Strategy (no heavy dependencies, works offline):
  1. Detect language via a character-frequency heuristic + Unicode block analysis.
     Falls back to "en" if uncertain.
  2. If non-English: transliterate/translate the message to English using
     the `deep-translator` library (GoogleTranslator, free, no API key).
     If deep-translator isn't installed: gracefully skip translation and
     set a flag so the UI can show a "translation unavailable" notice.
  3. The English translation is what flows through the agent pipeline
     (guardrails apply identically to all languages).
  4. After draft_resolution: translate the English response back to the
     detected language so the customer receives a reply in their language.

Supported languages: any language Google Translate supports.
Guardrails are NEVER bypassed — injection patterns are checked on both
the original and the translated English text.

State keys added:
  detected_language    : str  e.g. "es", "fr", "hi", "en"
  translated_to_english: bool
  original_message     : str  (preserved for audit)
"""

import re
import sys
from pathlib import Path
from logs.audit import write_audit_event

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Optional deep-translator import ───────────────────────────────────────
try:
    from deep_translator import GoogleTranslator
    _TRANSLATOR_AVAILABLE = True
except ImportError:
    _TRANSLATOR_AVAILABLE = False

# ── Language detection heuristics ─────────────────────────────────────────
# Map of Unicode ranges to probable language tags
_SCRIPT_RANGES = [
    (0x0900, 0x097F, "hi"),   # Devanagari → Hindi
    (0x0600, 0x06FF, "ar"),   # Arabic
    (0x4E00, 0x9FFF, "zh"),   # CJK Unified → Chinese
    (0x3040, 0x30FF, "ja"),   # Hiragana/Katakana → Japanese
    (0xAC00, 0xD7AF, "ko"),   # Hangul → Korean
    (0x0400, 0x04FF, "ru"),   # Cyrillic → Russian
    (0x0370, 0x03FF, "el"),   # Greek
    (0x0E00, 0x0E7F, "th"),   # Thai
]

# Common non-English function words (quick short-text detector)
_LANG_WORDS: dict[str, list[str]] = {
    "es": ["hola", "gracias", "dónde", "donde", "pedido", "por favor", "quiero", "mi"],
    "fr": ["bonjour", "merci", "où", "commande", "s'il vous", "mon", "je", "vous"],
    "de": ["bitte", "danke", "wo", "bestellung", "meine", "ich", "nicht", "haben"],
    "pt": ["olá", "obrigado", "onde", "pedido", "por favor", "quero", "meu"],
    "it": ["ciao", "grazie", "dove", "ordine", "per favore", "voglio", "mio"],
    "hi": ["नमस्ते", "धन्यवाद", "कहाँ", "ऑर्डर", "कृपया", "मेरा", "चाहिए"],
    "ar": ["مرحبا", "شكرا", "أين", "طلب", "من فضلك", "أريد", "بلدي"],
    "zh": ["你好", "谢谢", "在哪里", "订单", "请", "我的", "想要"],
    "ru": ["привет", "спасибо", "где", "заказ", "пожалуйста", "мой", "хочу"],
}


def detect_language(text: str) -> str:
    """
    Detect the probable language of *text*.
    Returns an ISO-639-1 code ('en', 'es', 'fr', etc.) or 'en' if uncertain.
    """
    # Script-range check (reliable for non-Latin scripts)
    for char in text:
        cp = ord(char)
        for lo, hi, lang in _SCRIPT_RANGES:
            if lo <= cp <= hi:
                return lang

    # Word-frequency check for Latin-script languages
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for lang, words in _LANG_WORDS.items():
        hits = sum(1 for w in words if w in text_lower)
        if hits:
            scores[lang] = hits

    if scores:
        best = max(scores, key=lambda k: scores[k])
        if scores[best] >= 1:
            return best

    return "en"


def translate_to_english(text: str, source_lang: str) -> str:
    """
    Translate *text* from *source_lang* to English.
    Returns original text if translation is unavailable.
    """
    if not _TRANSLATOR_AVAILABLE or source_lang == "en":
        return text
    try:
        return GoogleTranslator(source=source_lang, target="en").translate(text) or text
    except Exception:
        return text


def translate_from_english(text: str, target_lang: str) -> str:
    """
    Translate *text* from English to *target_lang*.
    Returns original text if translation is unavailable.
    """
    if not _TRANSLATOR_AVAILABLE or target_lang == "en":
        return text
    try:
        return GoogleTranslator(source="en", target=target_lang).translate(text) or text
    except Exception:
        return text


def process_incoming(message: str) -> dict:
    """
    Detect language and translate to English if needed.
    Returns dict with: detected_language, translated_to_english,
    original_message, english_message.
    """
    lang = detect_language(message)
    translated = (lang != "en")
    english = translate_to_english(message, lang) if translated else message

    write_audit_event({
        "event":              "language_detection",
        "detected_language":  lang,
        "translated":         translated,
        "translator_available": _TRANSLATOR_AVAILABLE,
        "original_preview":   message[:80],
        "english_preview":    english[:80],
    })

    return {
        "detected_language":     lang,
        "translated_to_english": translated,
        "original_message":      message,
        "english_message":       english,
    }


def translate_response(response: str, target_lang: str) -> str:
    """Translate *response* from English to *target_lang* for the customer."""
    if target_lang == "en" or not _TRANSLATOR_AVAILABLE:
        return response
    translated = translate_from_english(response, target_lang)
    write_audit_event({
        "event":       "response_translated",
        "target_lang": target_lang,
        "original_len": len(response),
        "translated_len": len(translated),
    })
    return translated
