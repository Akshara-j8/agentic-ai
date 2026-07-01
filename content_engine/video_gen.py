"""Promotional video generation via OpenRouter — Wan 2.7 image-to-video."""

import base64
import time

import requests

import config

_MAX_RETRIES = 3
_RETRY_DELAY = 3
_POLL_INTERVAL = 15   # seconds between polls
_POLL_TIMEOUT = 600   # 10 minutes max

_MOTION_PROMPT = (
    "Slow cinematic push-in. Subtle camera movement. "
    "Soft lighting. Gentle depth of field. Background mostly static."
)

_HEADERS = {
    "Authorization": f"Bearer {config.OPENROUTER_VIDEO_API_KEY}",
    "Content-Type": "application/json",
}

_BASE_URL = "https://openrouter.ai/api/v1"


def _submit(image_bytes: bytes) -> tuple[str, str]:
    """
    Submit image-to-video job to OpenRouter Wan 2.7.

    Args:
        image_bytes: Raw PNG bytes of the hero image.

    Returns:
        Tuple of (job_id, polling_url).
    """
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "model": "alibaba/wan-2.7",
        "prompt": _MOTION_PROMPT,
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "frame_images": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                "frame_type": "first_frame",
            }
        ],
    }
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{_BASE_URL}/videos",
                headers=_HEADERS,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["id"], data["polling_url"]
        except Exception as exc:
            if attempt == _MAX_RETRIES:
                raise RuntimeError(f"Video submission failed: {exc}") from exc
            time.sleep(_RETRY_DELAY * attempt)


def _poll(polling_url: str) -> str:
    """
    Poll job until completed and return the video content URL.

    Args:
        polling_url: URL returned from job submission.

    Returns:
        URL to download the generated video.

    Raises:
        RuntimeError: On job failure or timeout.
    """
    deadline = time.time() + _POLL_TIMEOUT
    while time.time() < deadline:
        try:
            resp = requests.get(polling_url, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")

            if status == "completed":
                return data["unsigned_urls"][0]
            if status == "failed":
                raise RuntimeError(f"Video job failed: {data.get('error', 'unknown')}")
        except RuntimeError:
            raise
        except Exception:
            pass  # transient — keep polling
        time.sleep(_POLL_INTERVAL)

    raise RuntimeError("Video generation timed out.")


def generate_promo_video(image_bytes: bytes) -> bytes:
    """
    Full pipeline: submit image-to-video → poll → download → return video bytes.

    Args:
        image_bytes: Raw PNG bytes of the hero image.

    Returns:
        Raw MP4 video bytes.
    """
    _, polling_url = _submit(image_bytes)
    video_url = _poll(polling_url)

    # Download the video (URL may require auth header)
    resp = requests.get(video_url, headers=_HEADERS, timeout=120)
    resp.raise_for_status()
    return resp.content
