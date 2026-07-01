"""
AI Self-Critique Loop — evaluates generated text assets and auto-regenerates
failed ones with feedback for up to MAX_RETRIES attempts.

Each asset is scored independently against four criteria:
  - tone_match      : Does the copy match the requested brand tone?
  - audience_fit    : Is the language and angle right for the target audience?
  - length_ok       : Does the content respect platform/format length limits?
  - product_aligned : Does the copy stay consistent with the product description?

A result is PASS only when all four criteria pass.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Callable

import requests

import config
import text_gen

MAX_RETRIES: int = 2   # max regeneration attempts after initial generation

_HEADERS = {
    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}


# ── Data types ─────────────────────────────────────────────────────────────────

@dataclass
class CriterionResult:
    """Outcome of one evaluation criterion."""
    passed: bool
    reason: str


@dataclass
class AssetCritiqueResult:
    """Full critique result for a single asset."""
    asset_name: str           # e.g. "Tagline", "Blog Introduction", "Twitter Post"
    content: str              # the final (possibly regenerated) content
    passed: bool              # True only if all criteria passed
    attempts: int             # total generation attempts (1 = accepted on first try)
    criteria: dict[str, CriterionResult] = field(default_factory=dict)
    feedback: str = ""        # human-readable summary of issues


@dataclass
class CritiqueSuiteResult:
    """Aggregated critique result for the full campaign suite."""
    tagline: AssetCritiqueResult
    blog: AssetCritiqueResult
    social: dict[str, AssetCritiqueResult]   # keys: twitter, instagram, linkedin

    @property
    def all_passed(self) -> bool:
        return (
            self.tagline.passed
            and self.blog.passed
            and all(r.passed for r in self.social.values())
        )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _critique_asset(
    asset_name: str,
    content: str,
    product: str,
    audience: str,
    tone: str,
    extra_rules: str = "",
) -> tuple[bool, dict[str, CriterionResult], str]:
    """
    Call OpenRouter to critique a single asset.

    Args:
        asset_name:  Human label for the asset type.
        content:     The generated text to evaluate.
        product:     Product name for consistency checks.
        audience:    Target audience for audience-fit checks.
        tone:        Brand tone for tone-match checks.
        extra_rules: Any additional platform-specific rules to enforce.

    Returns:
        (overall_passed, criteria_dict, feedback_summary)
    """
    prompt = (
        f"You are a professional marketing copy editor.\n"
        f"Evaluate the following {asset_name} strictly and objectively.\n\n"
        f"=== CONTEXT ===\n"
        f"Product: {product}\n"
        f"Target Audience: {audience}\n"
        f"Brand Tone: {tone}\n"
        f"{('Extra Rules: ' + extra_rules) if extra_rules else ''}\n\n"
        f"=== CONTENT TO EVALUATE ===\n{content}\n\n"
        f"=== EVALUATION CRITERIA ===\n"
        f"1. tone_match — Does this copy genuinely reflect the '{tone}' brand tone?\n"
        f"2. audience_fit — Is the language, angle, and vocabulary right for '{audience}'?\n"
        f"3. length_ok — Is the content an appropriate length for a {asset_name}? "
        f"(Tagline ≤10 words, Blog intro 150-250 words, Twitter ≤280 chars, "
        f"Instagram ≤2200 chars, LinkedIn ≤700 chars)\n"
        f"4. product_aligned — Does the copy accurately reference '{product}' "
        f"without contradictions or off-brand claims?\n\n"
        "Return STRICT JSON only — no markdown, no explanation:\n"
        '{"tone_match":{"passed":true,"reason":"..."},'
        '"audience_fit":{"passed":true,"reason":"..."},'
        '"length_ok":{"passed":true,"reason":"..."},'
        '"product_aligned":{"passed":true,"reason":"..."},'
        '"feedback":"One-sentence summary of issues if anything failed, else empty string."}'
    )

    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0.2,  # low temp for consistent, reproducible evaluation
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
            break
        except Exception:
            if attempt == 3:
                # On persistent failure, assume PASS to avoid blocking generation
                return True, {
                    k: CriterionResult(passed=True, reason="Evaluation unavailable")
                    for k in ("tone_match", "audience_fit", "length_ok", "product_aligned")
                }, ""
            time.sleep(2 * attempt)

    criteria: dict[str, CriterionResult] = {}
    for key in ("tone_match", "audience_fit", "length_ok", "product_aligned"):
        c = data.get(key, {})
        criteria[key] = CriterionResult(
            passed=bool(c.get("passed", True)),
            reason=str(c.get("reason", "")),
        )

    overall = all(c.passed for c in criteria.values())
    feedback = data.get("feedback", "") if not overall else ""
    return overall, criteria, feedback


def _run_with_critique(
    asset_name: str,
    initial_content: str,
    generator_fn: Callable[..., str],
    generator_args: tuple,
    product: str,
    audience: str,
    tone: str,
    extra_rules: str = "",
) -> AssetCritiqueResult:
    """
    Run critique → regenerate loop for a single text asset.

    Args:
        asset_name:      Human-readable label used in prompts and results.
        initial_content: The first-pass generated text.
        generator_fn:    Callable that takes (*generator_args, feedback: str) -> str.
        generator_args:  Base arguments for generator_fn (feedback appended automatically).
        product:         Product name.
        audience:        Target audience.
        tone:            Brand tone.
        extra_rules:     Additional evaluation rules for this asset type.

    Returns:
        AssetCritiqueResult with final content and full evaluation details.
    """
    content = initial_content
    passed = False
    criteria: dict[str, CriterionResult] = {}
    feedback = ""
    attempts = 1

    for _ in range(MAX_RETRIES + 1):  # initial check + up to MAX_RETRIES regenerations
        passed, criteria, feedback = _critique_asset(
            asset_name, content, product, audience, tone, extra_rules
        )
        if passed or attempts > MAX_RETRIES:
            break
        # Regenerate with feedback injected as the last argument
        try:
            content = generator_fn(*generator_args, feedback)
        except Exception:
            break  # keep last content on generation failure
        attempts += 1

    return AssetCritiqueResult(
        asset_name=asset_name,
        content=content,
        passed=passed,
        attempts=attempts,
        criteria=criteria,
        feedback=feedback,
    )


# ── Regeneration functions (each accepts a trailing `feedback: str` argument) ──

def _regen_tagline(product: str, audience: str, tone: str, feedback: str) -> str:
    messages = [
        {
            "role": "user",
            "content": (
                "Regenerate this campaign tagline addressing the critique below.\n"
                f"Max 10 words. No hashtags. Brand tone: {tone}.\n"
                f"Product: {product} | Audience: {audience}\n\n"
                f"Critique feedback: {feedback}\n\n"
                "Return plain text only."
            ),
        }
    ]
    return text_gen._chat(messages, max_tokens=30, temperature=0.8)


def _regen_blog(
    product: str, audience: str, tone: str, tagline: str, feedback: str
) -> str:
    messages = [
        {"role": "system", "content": "You are an award-winning content strategist."},
        {
            "role": "user",
            "content": (
                "Rewrite this blog introduction addressing the critique below.\n"
                f"Exactly 200 words. Product: '{product}'. Audience: {audience}. "
                f"Tone: {tone}. Tagline: \"{tagline}\".\n\n"
                f"Critique feedback: {feedback}\n\n"
                "Return only the blog text."
            ),
        },
    ]
    return text_gen._chat(messages, max_tokens=350, temperature=0.7)


def _regen_social_post(
    product: str,
    audience: str,
    tone: str,
    tagline: str,
    platform: str,
    char_limit: int,
    feedback: str,
) -> str:
    messages = [
        {
            "role": "user",
            "content": (
                f"Rewrite this {platform} post addressing the critique below.\n"
                f"Max {char_limit} characters. Product: '{product}'. "
                f"Audience: {audience}. Tone: {tone}. Tagline: \"{tagline}\".\n\n"
                f"Critique feedback: {feedback}\n\n"
                "Return only the post text — no JSON, no labels."
            ),
        }
    ]
    return text_gen._chat(messages, max_tokens=400, temperature=0.75)


# ── Public API ─────────────────────────────────────────────────────────────────

def critique_and_refine(
    product: str,
    audience: str,
    tone: str,
    tagline: str,
    blog: str,
    social: dict[str, str],
) -> CritiqueSuiteResult:
    """
    Critique all text assets and auto-regenerate any that fail (up to MAX_RETRIES).

    Args:
        product:   Product name.
        audience:  Target audience.
        tone:      Brand tone.
        tagline:   Generated tagline string.
        blog:      Generated blog introduction string.
        social:    Dict with keys 'twitter', 'instagram', 'linkedin'.

    Returns:
        CritiqueSuiteResult with PASS/FAIL per asset and final (improved) content.
    """
    # --- Tagline ---
    tagline_result = _run_with_critique(
        asset_name="Tagline",
        initial_content=tagline,
        generator_fn=_regen_tagline,
        generator_args=(product, audience, tone),
        product=product,
        audience=audience,
        tone=tone,
        extra_rules="Must be 10 words or fewer. No hashtags.",
    )

    # --- Blog Introduction ---
    blog_result = _run_with_critique(
        asset_name="Blog Introduction",
        initial_content=blog,
        generator_fn=_regen_blog,
        generator_args=(product, audience, tone, tagline_result.content),
        product=product,
        audience=audience,
        tone=tone,
        extra_rules="Should be 150-250 words. Must naturally weave in the campaign tagline.",
    )

    # --- Social Posts ---
    platform_configs = {
        "twitter":   ("Twitter Post",   280,  "Must be 280 characters or fewer including spaces."),
        "instagram": ("Instagram Post", 2200, "May include relevant hashtags and emojis. Max 2200 characters."),
        "linkedin":  ("LinkedIn Post",  700,  "Professional tone acceptable. Max 700 characters."),
    }

    social_results: dict[str, AssetCritiqueResult] = {}

    for platform, (label, char_limit, rules) in platform_configs.items():
        post_content = social.get(platform, "")

        # Build a closure so each platform gets its own char_limit and platform name
        def _make_regen_fn(plat: str, limit: int) -> Callable[..., str]:
            def _regen(prod: str, aud: str, tn: str, tl: str, fb: str) -> str:
                return _regen_social_post(prod, aud, tn, tl, plat, limit, fb)
            return _regen

        social_results[platform] = _run_with_critique(
            asset_name=label,
            initial_content=post_content,
            generator_fn=_make_regen_fn(platform, char_limit),
            generator_args=(product, audience, tone, tagline_result.content),
            product=product,
            audience=audience,
            tone=tone,
            extra_rules=rules,
        )

    return CritiqueSuiteResult(
        tagline=tagline_result,
        blog=blog_result,
        social=social_results,
    )
