"""CreativeProvider — image/video generation behind a swappable interface (PRD §7.5).

MOCK returns deterministic placeholders stored via AssetStore (no external calls). The
real provider generates images with Gemini Imagen and UGC video with fal.ai (Kling), each
falling back to the mock if its key is absent — so partial config still works and callers
never break.
"""
from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from typing import Any

from leadpilot.common.config import settings
from leadpilot.common.logging import get_logger
from leadpilot.saathi.providers.assets import get_asset_store

log = get_logger("creative")


class CreativeProvider:
    def generate_image(self, *, prompt: str, ratio: str = "4:5") -> str:
        raise NotImplementedError

    def generate_video(self, *, script: str, ratio: str = "9:16") -> str:
        """UGC-style short video from a script. Sustained scroll-stopping creative is what
        keeps click-through (and therefore leads) from decaying."""
        raise NotImplementedError


class MockCreativeProvider(CreativeProvider):
    def generate_image(self, *, prompt: str, ratio: str = "4:5") -> str:
        key = "creatives/" + hashlib.sha256(f"{prompt}:{ratio}".encode()).hexdigest()[:16] + ".png"
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
            "00000049454e44ae426082"
        )
        return get_asset_store().put_bytes(key, png, "image/png")

    def generate_video(self, *, script: str, ratio: str = "9:16") -> str:
        key = "creatives/" + hashlib.sha256(f"{script}:{ratio}".encode()).hexdigest()[:16] + ".mp4"
        mp4 = bytes.fromhex("0000001c66747970697736320000000069736f6d69736f326d703431")
        return get_asset_store().put_bytes(key, mp4, "video/mp4")


def fal_generate_video_bytes(
    script: str,
    *,
    ratio: str,
    api_key: str,
    model: str,
    client: Any,
    duration: str = "5",
    poll_timeout_s: float = 180.0,
    poll_interval_s: float = 3.0,
    sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    """Run one fal.ai queue job end-to-end and return the rendered MP4 bytes.

    fal's queue API: submit → poll status until COMPLETED → fetch the result → download the
    video URL. `client` is an httpx.Client (injected so tests drive it with a MockTransport).
    """
    headers = {"Authorization": f"Key {api_key}"}
    submit = client.post(
        f"https://queue.fal.run/{model}",
        headers=headers,
        json={"prompt": script, "aspect_ratio": ratio, "duration": duration},
    )
    submit.raise_for_status()
    job = submit.json()
    status_url = job["status_url"]
    response_url = job["response_url"]

    waited = 0.0
    while True:
        status = client.get(status_url, headers=headers).json().get("status")
        if status == "COMPLETED":
            break
        if status in {"FAILED", "ERROR"}:
            raise RuntimeError(f"fal video job failed: {status}")
        if waited >= poll_timeout_s:
            raise TimeoutError("fal video generation timed out")
        sleep(poll_interval_s)
        waited += poll_interval_s

    result = client.get(response_url, headers=headers).json()
    video_url = result["video"]["url"]  # Kling/text-to-video output shape
    return client.get(video_url).content


class RealCreativeProvider(CreativeProvider):
    def generate_image(self, *, prompt: str, ratio: str = "4:5") -> str:
        if not settings.gemini_api_key:  # pragma: no cover
            return MockCreativeProvider().generate_image(prompt=prompt, ratio=ratio)
        import google.generativeai as genai  # pragma: no cover - requires key

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.ImageGenerationModel("imagen-3.0-generate-001")
        result = model.generate_images(prompt=prompt, number_of_images=1, aspect_ratio=ratio)
        data = result.images[0]._image_bytes  # noqa: SLF001 - SDK accessor
        key = "creatives/" + hashlib.sha256(prompt.encode()).hexdigest()[:16] + ".png"
        return get_asset_store().put_bytes(key, data, "image/png")

    def generate_video(self, *, script: str, ratio: str = "9:16") -> str:
        if not settings.fal_api_key:
            return MockCreativeProvider().generate_video(script=script, ratio=ratio)
        import httpx  # pragma: no cover - requires key

        try:  # pragma: no cover - requires key
            with httpx.Client(timeout=settings.llm_request_timeout_s) as client:
                data = fal_generate_video_bytes(
                    script, ratio=ratio, api_key=settings.fal_api_key,
                    model=settings.fal_video_model, duration=settings.fal_video_duration,
                    poll_timeout_s=settings.fal_poll_timeout_s,
                    poll_interval_s=settings.fal_poll_interval_s, client=client)
            key = "creatives/" + hashlib.sha256(script.encode()).hexdigest()[:16] + ".mp4"
            return get_asset_store().put_bytes(key, data, "video/mp4")
        except Exception as exc:  # noqa: BLE001 - never fail the batch on a video hiccup
            log.warning("fal_video_failed", error=str(exc)[:200])
            return MockCreativeProvider().generate_video(script=script, ratio=ratio)


_provider: CreativeProvider | None = None


def get_creative_provider() -> CreativeProvider:
    global _provider
    if _provider is None:
        if settings.mock_llm or not (settings.gemini_api_key or settings.fal_api_key):
            _provider = MockCreativeProvider()
        else:  # pragma: no cover - requires keys
            _provider = RealCreativeProvider()
    return _provider
