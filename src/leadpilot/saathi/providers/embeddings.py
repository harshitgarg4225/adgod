"""EmbeddingProvider — vectors for semantic memory (PRD §4.4).

MOCK produces deterministic 1536-d unit vectors from text (no API), so retrieval is
testable offline. Real provider (Gemini/text-embedding) slots in behind the interface.
"""
from __future__ import annotations

import hashlib
import math

from leadpilot.common.config import settings

DIM = 1536


class EmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class MockEmbeddingProvider(EmbeddingProvider):
    def embed(self, text: str) -> list[float]:
        # Deterministic pseudo-embedding: seed an LCG from the text hash, fill + normalize.
        seed = int(hashlib.sha256((text or "").encode()).hexdigest()[:16], 16) or 1
        vec: list[float] = []
        x = seed
        for _ in range(DIM):
            x = (1103515245 * x + 12345) & 0x7FFFFFFF
            vec.append((x / 0x3FFFFFFF) - 1.0)  # in [-1, 1]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class GeminiEmbeddingProvider(EmbeddingProvider):  # pragma: no cover - requires key
    def embed(self, text: str) -> list[float]:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        res = genai.embed_content(model="models/text-embedding-004", content=text or "")
        return res["embedding"]


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        if settings.mock_llm or not settings.gemini_api_key:
            _provider = MockEmbeddingProvider()
        else:  # pragma: no cover
            _provider = GeminiEmbeddingProvider()
    return _provider
