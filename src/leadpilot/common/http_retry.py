"""Outbound HTTP resilience: retry with backoff that honours Retry-After, plus a tiny
per-endpoint circuit breaker.

Meta/WhatsApp/Razorpay aggressively rate-limit; ignoring 429 + Retry-After makes the
outbox hammer them and extends bans. This wraps a single request so transient 429/5xx are
retried with backoff, and repeated failures trip a breaker that fails fast for a cooldown
instead of piling on a struggling upstream.
"""
from __future__ import annotations

import email.utils
import time
from collections.abc import Callable
from typing import Any

from leadpilot.common.logging import get_logger

log = get_logger("http_retry")

_RETRYABLE = {429, 500, 502, 503, 504}


def parse_retry_after(value: str | None) -> float | None:
    """Retry-After may be seconds or an HTTP date. Return seconds, or None if unparseable."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    dt = email.utils.parsedate_to_datetime(value)
    if dt is None:
        return None
    import datetime as _dt

    now = _dt.datetime.now(_dt.UTC) if dt.tzinfo else _dt.datetime.now()
    return max(0.0, (dt - now).total_seconds())


def request_with_retry(
    do_request: Callable[[], Any],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Call ``do_request`` (a no-arg callable returning an httpx.Response-like object),
    retrying retryable statuses. Honours Retry-After; caps the backoff at ``max_delay``."""
    last = None
    for attempt in range(max_attempts):
        resp = do_request()
        last = resp
        status = getattr(resp, "status_code", 200)
        if status not in _RETRYABLE:
            return resp
        if attempt == max_attempts - 1:
            break
        retry_after = parse_retry_after(_header(resp, "Retry-After"))
        delay = retry_after if retry_after is not None else base_delay * (2 ** attempt)
        delay = min(delay, max_delay)
        log.warning("http_retry", status=status, attempt=attempt + 1, delay=round(delay, 2))
        sleep(delay)
    return last


def _header(resp: Any, name: str) -> str | None:
    headers = getattr(resp, "headers", None)
    if headers is None:
        return None
    try:
        return headers.get(name)
    except AttributeError:
        return None


class CircuitBreaker:
    """Trip open after ``threshold`` consecutive failures; fail fast for ``cooldown`` s."""

    def __init__(self, *, threshold: int = 5, cooldown: float = 30.0,
                 now: Callable[[], float] = time.monotonic) -> None:
        self._threshold = threshold
        self._cooldown = cooldown
        self._now = now
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if self._now() - self._opened_at >= self._cooldown:
            # Half-open: allow one trial through.
            self._opened_at = None
            self._failures = 0
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._opened_at = self._now()
