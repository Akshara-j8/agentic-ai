"""AI Content Engine — Streamlit application entry point.

Features:
  - Core campaign generation: tagline, blog intro, social posts, hero image, promo video.
  - AI Self-Critique Loop  : PASS/FAIL panel per asset with auto-regeneration feedback.
  - Voiceover Generation   : Blog → narration script → MP3 audio player + download.
  - Multi-Channel Adaptation: Dropdown to rewrite text assets for Gen-Z TikTok,
                              B2B LinkedIn, or Parents Facebook; images/video unchanged.

Session-state design
--------------------
All generated assets are written to st.session_state under the key "campaign" so
they survive Streamlit reruns triggered by widget interactions (e.g. dropdown
changes, button clicks). The channel adaptation section is rendered outside the
`if generate:` block so it never disappears when the user interacts with it.
"""

import streamlit as st

import channel_adapter
import config  # validates env vars on import
import critique
import image_gen
import text_gen
import video_gen
import voiceover

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Content Engine",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 AI Content Engine")
st.caption("Generate a complete marketing campaign from a single product brief.")

# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📋 Product Brief")
    product = st.text_input("Product Name", placeholder="e.g. AquaPure Water Bottle")
    audience = st.text_input("Target Audience", placeholder="e.g. Fitness enthusiasts aged 25-40")
    tone = st.selectbox(
        "Brand Tone",
        ["Premium", "Eco", "Playful", "Minimal", "Luxury", "Modern"],
    )

    st.divider()
    st.subheader("⚙️ Options")
    enable_critique = st.checkbox("🧠 AI Self-Critique & Auto-Refinement", value=True)
    enable_voiceover = st.checkbox("🎙️ Generate Voiceover (MP3)", value=True)

    st.divider()
    generate = st.button("✨ Generate Campaign Suite", use_container_width=True, type="primary")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_inputs() -> bool:
    """Validate sidebar inputs and show warnings if incomplete."""
    if not product.strip():
        st.warning("Please enter a Product Name.")
        return False
    if not audience.strip():
        st.warning("Please enter a Target Audience.")
        return False
    return True


def _run_step(label: str, spinner_text: str, fn, *args):
    """
    Run a generation step inside a spinner; surface errors via st.error.

    Returns the result of fn(*args), or None on failure.
    """
    with st.spinner(spinner_text):
        try:
            return fn(*args)
        except Exception as exc:
            st.error(f"**{label} failed:** {exc}")
            return None


# ── Critique panel rendering ──────────────────────────────────────────────────

def _badge(passed: bool) -> str:
    return "✅ PASS" if passed else "❌ FAIL"


def _render_critique_panel(suite: critique.CritiqueSuiteResult) -> None:
    """Render the full self-critique panel in a collapsible expander."""
    overall_icon = "✅" if suite.all_passed else "⚠️"
    overall_label = "All assets passed" if suite.all_passed else "Some assets were refined"

    with st.expander(
        f"🧠 AI Self-Critique Report — {overall_icon} {overall_label}",
        expanded=not suite.all_passed,
    ):
        assets_to_show: list[critique.AssetCritiqueResult] = [
            suite.tagline,
            suite.blog,
            *suite.social.values(),
        ]

        for asset in assets_to_show:
            col_name, col_status = st.columns([3, 1])
            with col_name:
                attempts_note = (
                    f" *(refined in {asset.attempts} attempt{'s' if asset.attempts > 1 else ''})*"
                    if asset.attempts > 1
                    else ""
                )
                st.markdown(f"**{asset.asset_name}**{attempts_note}")
            with col_status:
                st.markdown(_badge(asset.passed))

            if asset.criteria:
                for key, label in [
                    ("tone_match",      "Tone Match"),
                    ("audience_fit",    "Audience Fit"),
                    ("length_ok",       "Length"),
                    ("product_aligned", "Product Alignment"),
                ]:
                    if key in asset.criteria:
                        cr = asset.criteria[key]
                        icon = "✅" if cr.passed else "❌"
                        st.markdown(f"{icon} **{label}** — {cr.reason}")

            if asset.feedback:
                st.caption(f"💬 Feedback applied: {asset.feedback}")

            st.divider()


# ── Channel adaptation panel rendering ───────────────────────────────────────

def _render_channel_adaptation() -> None:
    """
    Render the multi-channel adaptation section.

    Reads source assets from st.session_state["campaign"] so it works
    independently of the generate button. The dropdown and Adapt button
    operate purely through session_state without re-triggering generation.
    """
    campaign = st.session_state.get("campaign")
    if campaign is None:
        return  # nothing generated yet — don't render the section at all

    original_tagline: str = campaign["tagline"]
    original_blog: str    = campaign["blog"]
    original_social: dict = campaign["social"]
    image_bytes: bytes | None = campaign.get("image_bytes")
    video_bytes: bytes | None = campaign.get("video_bytes")

    st.divider()
    st.subheader("📡 Multi-Channel Adaptation")
    st.caption("Rewrite text assets for a specific platform audience. Image and video remain unchanged.")

    channel_options_label_to_key: dict[str, str] = {
        v: k for k, v in channel_adapter.CHANNELS.items()
    }
    channel_labels = list(channel_options_label_to_key.keys())

    col_select, col_btn = st.columns([3, 1], vertical_alignment="bottom")
    with col_select:
        selected_label = st.selectbox(
            "Target Channel",
            options=channel_labels,
            index=0,
            key="channel_select",
        )
    with col_btn:
        adapt_clicked = st.button(
            f"🔄 Adapt",
            key="adapt_btn",
            type="secondary",
            use_container_width=True,
        )

    selected_key = channel_options_label_to_key[selected_label]

    if adapt_clicked:
        with st.spinner(f"Adapting content for {selected_label}…"):
            try:
                adapted = channel_adapter.adapt_for_channel(
                    channel_key=selected_key,
                    product=campaign["product"],
                    audience=campaign["audience"],
                    tone=campaign["tone"],
                    tagline=original_tagline,
                    blog=original_blog,
                    social=original_social,
                )
                # Store the adapted result keyed by channel so switching back
                # to a previously adapted channel shows cached results instantly
                if "adapted_cache" not in st.session_state:
                    st.session_state["adapted_cache"] = {}
                st.session_state["adapted_cache"][selected_key] = adapted
                st.session_state["last_adapted_key"] = selected_key
            except Exception as exc:
                st.error(f"Channel adaptation failed: {exc}")

    # Retrieve from cache if available for the currently selected channel
    adapted_cache: dict = st.session_state.get("adapted_cache", {})
    adapted: channel_adapter.AdaptedAssets | None = adapted_cache.get(selected_key)

    if adapted is None:
        st.info(f"Click **🔄 Adapt** to rewrite assets for **{selected_label}**.")
        return

    st.success(f"✨ Content adapted for **{adapted.channel_label}**")

    orig_col, adapted_col = st.columns(2, gap="large")

    with orig_col:
        st.markdown("##### 📄 Original")

        st.markdown("**Tagline**")
        st.markdown(f"> {original_tagline}")

        st.markdown("**Blog Introduction**")
        st.text_area(
            "orig_blog_display",
            original_blog,
            height=180,
            label_visibility="collapsed",
            key="orig_blog_display",
            disabled=True,
        )

        st.markdown("**Social Posts**")
        o_tw, o_ig, o_li = st.tabs(["𝕏 Twitter", "📸 Instagram", "💼 LinkedIn"])
        with o_tw:
            st.text_area(
                "orig_tw_d", original_social.get("twitter", ""),
                height=100, label_visibility="collapsed", key="orig_tw_d", disabled=True,
            )
        with o_ig:
            st.text_area(
                "orig_ig_d", original_social.get("instagram", ""),
                height=150, label_visibility="collapsed", key="orig_ig_d", disabled=True,
            )
        with o_li:
            st.text_area(
                "orig_li_d", original_social.get("linkedin", ""),
                height=120, label_visibility="collapsed", key="orig_li_d", disabled=True,
            )

    with adapted_col:
        st.markdown(f"##### 🎯 Adapted — {adapted.channel_label}")

        st.markdown("**Tagline**")
        st.markdown(f"> {adapted.tagline}")

        st.markdown("**Blog Introduction**")
        st.text_area(
            "adp_blog_display",
            adapted.blog,
            height=180,
            label_visibility="collapsed",
            key="adp_blog_display",
        )

        st.markdown("**Social Posts**")
        a_tw, a_ig, a_li = st.tabs(["𝕏 Twitter", "📸 Instagram", "💼 LinkedIn"])
        with a_tw:
            adp_tw = adapted.social.get("twitter", "")
            st.text_area("adp_tw_d", adp_tw, height=100,
                         label_visibility="collapsed", key="adp_tw_d")
            st.caption(f"{len(adp_tw)} / 280 characters")
        with a_ig:
            adp_ig = adapted.social.get("instagram", "")
            st.text_area("adp_ig_d", adp_ig, height=150,
                         label_visibility="collapsed", key="adp_ig_d")
            st.caption(f"{len(adp_ig)} / 2200 characters")
        with a_li:
            adp_li = adapted.social.get("linkedin", "")
            st.text_area("adp_li_d", adp_li, height=120,
                         label_visibility="collapsed", key="adp_li_d")
            st.caption(f"{len(adp_li)} / 700 characters")

    # Image and video — pass-through, displayed below the text comparison
    if image_bytes or video_bytes:
        st.markdown("---")
        st.caption("🖼️ Image and 🎬 video assets are **unchanged** across all channels.")
        media_col1, media_col2 = st.columns(2, gap="large")
        with media_col1:
            if image_bytes:
                st.image(image_bytes, use_container_width=True, caption="Hero Image (unchanged)")
        with media_col2:
            if video_bytes:
                st.video(video_bytes, format="video/mp4")
                st.download_button(
                    "⬇️ Download Video",
                    video_bytes,
                    "promo_video.mp4",
                    "video/mp4",
                    key="channel_video_dl",
                )


# ── Main generation flow ──────────────────────────────────────────────────────

if generate:
    if not _require_inputs():
        st.stop()

    # Reset all session state from a previous run
    for key in ("campaign", "adapted_cache", "last_adapted_key"):
        st.session_state.pop(key, None)

    left, right = st.columns(2, gap="large")

    # STEP 1 — Tagline
    tagline = _run_step(
        "Tagline generation",
        "🖊️ Step 1/5 — Crafting campaign tagline…",
        text_gen.generate_tagline,
        product, audience, tone,
    )
    if tagline is None:
        st.stop()

    # STEP 2 — Blog intro
    blog = _run_step(
        "Blog introduction",
        "📝 Step 2/5 — Writing blog introduction…",
        text_gen.generate_blog_intro,
        product, audience, tone, tagline,
    )
    if blog is None:
        st.stop()

    # STEP 3 — Social posts
    social = _run_step(
        "Social media posts",
        "📱 Step 3/5 — Generating social media posts…",
        text_gen.generate_social_posts,
        product, audience, tone, tagline,
    )
    if social is None:
        st.stop()

    # STEP 4 — Hero image
    image_bytes = None
    if config.OPENROUTER_IMAGE_API_KEY:
        image_bytes = _run_step(
            "Hero image",
            "🎨 Step 4/5 — Generating hero image…",
            image_gen.generate_hero_image,
            product, audience, tone, tagline,
        )

    # STEP 5 — Promo video
    video_bytes = None
    if image_bytes and config.OPENROUTER_VIDEO_API_KEY:
        video_bytes = _run_step(
            "Promotional video",
            "🎬 Step 5/5 — Generating promotional video via Wan 2.7 (may take ~2 min)…",
            video_gen.generate_promo_video,
            image_bytes,
        )

    # ── AI Self-Critique ──────────────────────────────────────────────────────
    critique_suite: critique.CritiqueSuiteResult | None = None
    if enable_critique:
        with st.spinner("🧠 Running AI self-critique and refining assets…"):
            try:
                critique_suite = critique.critique_and_refine(
                    product=product,
                    audience=audience,
                    tone=tone,
                    tagline=tagline,
                    blog=blog,
                    social=social,
                )
                tagline = critique_suite.tagline.content
                blog    = critique_suite.blog.content
                social  = {k: v.content for k, v in critique_suite.social.items()}
            except Exception as exc:
                st.warning(f"Self-critique encountered an error and was skipped: {exc}")

    # ── Voiceover ─────────────────────────────────────────────────────────────
    narration_script: str | None = None
    mp3_bytes: bytes | None = None
    if enable_voiceover:
        with st.spinner("🎙️ Generating voiceover narration script and MP3…"):
            try:
                narration_script, mp3_bytes = voiceover.generate_voiceover(
                    blog=blog,
                    product=product,
                    audience=audience,
                    tone=tone,
                )
            except Exception as exc:
                st.warning(f"Voiceover generation encountered an error and was skipped: {exc}")

    # ── Persist everything to session_state ───────────────────────────────────
    # This is the key step: all generated assets are stored so that subsequent
    # reruns (from widget interactions) can still access them.
    st.session_state["campaign"] = {
        "product":          product,
        "audience":         audience,
        "tone":             tone,
        "tagline":          tagline,
        "blog":             blog,
        "social":           social,
        "image_bytes":      image_bytes,
        "video_bytes":      video_bytes,
        "narration_script": narration_script,
        "mp3_bytes":        mp3_bytes,
        "critique_suite":   critique_suite,
    }

    # ── Render core results ───────────────────────────────────────────────────
    with left:
        st.subheader("🏷️ Campaign Tagline")
        st.markdown(f"> **{tagline}**")

        st.divider()
        st.subheader("📰 Blog Introduction")
        st.markdown(blog)

        if narration_script or mp3_bytes:
            st.divider()
            st.subheader("🎙️ Voiceover")
            if narration_script:
                with st.expander("📜 View Narration Script", expanded=False):
                    display_script = narration_script.replace("[PAUSE]", " `[PAUSE]` ")
                    st.markdown(display_script)
            if mp3_bytes:
                st.audio(mp3_bytes, format="audio/mp3")
                st.download_button(
                    label="⬇️ Download Narration MP3",
                    data=mp3_bytes,
                    file_name="voiceover_narration.mp3",
                    mime="audio/mp3",
                    key="voiceover_dl",
                )

        st.divider()
        st.subheader("📱 Social Media Posts")
        tab_tw, tab_ig, tab_li = st.tabs(["𝕏 Twitter", "📸 Instagram", "💼 LinkedIn"])
        with tab_tw:
            st.text_area("Twitter", social.get("twitter", ""), height=120, label_visibility="collapsed")
            st.caption(f"{len(social.get('twitter', ''))} / 280 characters")
        with tab_ig:
            st.text_area("Instagram", social.get("instagram", ""), height=200, label_visibility="collapsed")
            st.caption(f"{len(social.get('instagram', ''))} / 2200 characters")
        with tab_li:
            st.text_area("LinkedIn", social.get("linkedin", ""), height=160, label_visibility="collapsed")
            st.caption(f"{len(social.get('linkedin', ''))} / 700 characters")

    with right:
        st.subheader("🖼️ Hero Image")
        if image_bytes:
            st.image(image_bytes, use_container_width=True)
        else:
            st.info("Hero image skipped — add OPENROUTER_IMAGE_API_KEY to .env to enable.")

        st.divider()
        st.subheader("🎬 Promotional Video")
        if video_bytes:
            st.video(video_bytes, format="video/mp4")
            st.download_button("⬇️ Download Video", video_bytes, "promo_video.mp4", "video/mp4")
        elif not config.OPENROUTER_VIDEO_API_KEY:
            st.info("Video skipped — add OPENROUTER_VIDEO_API_KEY to .env to enable.")
        else:
            st.info("Video generation did not complete. Check the error above.")

    st.success("🎉 Campaign suite generated successfully!")

    if critique_suite is not None:
        st.divider()
        _render_critique_panel(critique_suite)


# ── Channel adaptation — always rendered outside generate block ───────────────
# Reads from st.session_state["campaign"], so it persists across all reruns.
# Dropdown changes and the Adapt button no longer cause the section to disappear.
_render_channel_adaptation()
