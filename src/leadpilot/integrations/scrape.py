"""Lightweight website scraper — pulls value props / testimonials / pricing text from the
business's own site to ground the Scout research (better creative than category guesses).

Mock-safe: returns "" unless a URL is given and scraping is enabled. Strips tags/scripts
and truncates, so only readable copy reaches the LLM (no markup, no injection surface).
"""
from __future__ import annotations

import re

from leadpilot.common.config import settings
from leadpilot.common.logging import get_logger

log = get_logger("scrape")

_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
_ANGLE_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def scrape_site(url: str | None, *, max_chars: int = 4000) -> str:
    """Return readable text from the page, or "" if no URL / scraping disabled / on error.
    Never raises — research must proceed even if the site is down."""
    if not url or settings.mock_meta:
        # In mock mode we don't make outbound calls; research falls back to the offer text.
        return ""
    try:  # pragma: no cover - requires network
        import httpx

        resp = httpx.get(url, timeout=settings.llm_request_timeout_s,
                         headers={"User-Agent": "SalmorBot/1.0"}, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        html = _TAG_RE.sub(" ", html)
        text = _ANGLE_RE.sub(" ", html)
        text = _WS_RE.sub(" ", text).strip()
        return text[:max_chars]
    except Exception as exc:  # noqa: BLE001 - best-effort enrichment
        log.warning("scrape_failed", url=url, error=str(exc)[:200])
        return ""
