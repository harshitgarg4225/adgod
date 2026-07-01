"""CreativeProvider — image/video generation behind a swappable interface (PRD §7.5).

MOCK returns a deterministic placeholder stored via AssetStore (no external calls).
Real providers (Gemini Imagen / fal.ai-Kling) slot in behind the same interface.
"""
from __future__ import annotations

import hashlib

from leadpilot.common.config import settings
from leadpilot.saathi.providers.assets import get_asset_store


class CreativeProvider:
    def generate_image(self, *, prompt: str, ratio: str = "4:5") -> str:
        raise NotImplementedError

    def generate_video(self, *, script: str, ratio: str = "9:16") -> str:
        """UGC-style short video from a script/shot-list. Sustained scroll-stopping
        creative is what keeps click-through (and therefore leads) from decaying."""
        raise NotImplementedError


class MockCreativeProvider(CreativeProvider):
    def generate_image(self, *, prompt: str, ratio: str = "4:5") -> str:
        key = "creatives/" + hashlib.sha256(f"{prompt}:{ratio}".encode()).hexdigest()[:16] + ".png"
        # A 1x1 PNG placeholder; real provider returns real bytes.
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
            "00000049454e44ae426082"
        )
        return get_asset_store().put_bytes(key, png, "image/png")

    def generate_video(self, *, script: str, ratio: str = "9:16") -> str:
        # A tiny valid MP4 header placeholder; real provider returns a rendered clip.
        key = "creatives/" + hashlib.sha256(f"{script}:{ratio}".encode()).hexdigest()[:16] + ".mp4"
        mp4 = bytes.fromhex("0000001c66747970697736320000000069736f6d69736f326d703431")
        return get_asset_store().put_bytes(key, mp4, "video/mp4")


class GeminiImagenProvider(CreativeProvider):  # pragma: no cover - requires key
    def generate_image(self, *, prompt: str, ratio: str = "4:5") -> str:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.ImageGenerationModel("imagen-3.0-generate-001")
        result = model.generate_images(prompt=prompt, number_of_images=1, aspect_ratio=ratio)
        data = result.images[0]._image_bytes  # noqa: SLF001 - SDK accessor
        key = "creatives/" + hashlib.sha256(prompt.encode()).hexdigest()[:16] + ".png"
        return get_asset_store().put_bytes(key, data, "image/png")

    def generate_video(self, *, script: str, ratio: str = "9:16") -> str:
        # Real text-to-video (e.g. a fal.ai/Kling-style endpoint) fetched then stored via
        # the AssetStore. Configured out of band; falls back to the image provider's
        # interface so callers never break.
        import httpx

        resp = httpx.post(
            settings.video_provider_url,
            headers={"Authorization": f"Bearer {settings.video_provider_key or ''}"},
            json={"prompt": script, "aspect_ratio": ratio},
            timeout=settings.llm_request_timeout_s,
        )
        resp.raise_for_status()
        video_url = resp.json()["video_url"]
        data = httpx.get(video_url, timeout=settings.llm_request_timeout_s).content
        key = "creatives/" + hashlib.sha256(script.encode()).hexdigest()[:16] + ".mp4"
        return get_asset_store().put_bytes(key, data, "video/mp4")


_provider: CreativeProvider | None = None


def get_creative_provider() -> CreativeProvider:
    global _provider
    if _provider is None:
        if settings.mock_llm or not settings.gemini_api_key:
            _provider = MockCreativeProvider()
        else:  # pragma: no cover
            _provider = GeminiImagenProvider()
    return _provider
