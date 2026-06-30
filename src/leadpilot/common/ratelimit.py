"""Redis fixed-window rate limiting (auth/OTP + webhooks).

Fail-open if Redis is unavailable (never block the lead path on a cache outage). Keys
are namespaced per action + identifier (phone/IP). Used as a FastAPI dependency and a
plain callable for webhook handlers.
"""
from __future__ import annotations

from leadpilot.common.config import settings
from leadpilot.common.errors import AppError
from leadpilot.common.logging import get_logger

log = get_logger("ratelimit")
_redis = None


class RateLimited(AppError):
    status_code = 429
    error_type = "https://leadpilot.app/errors/rate-limited"
    title = "Too Many Requests"
    user_message_key = "error.generic"


def _client():
    global _redis
    if _redis is None:
        try:
            import redis

            _redis = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        except Exception:  # pragma: no cover
            _redis = False
    return _redis or None


def allow(action: str, identifier: str, *, limit: int, window_s: int) -> bool:
    """Return True if under the limit. Fail-open on Redis errors."""
    client = _client()
    if client is None:
        return True
    key = f"rl:{action}:{identifier}"
    try:
        n = client.incr(key)
        if n == 1:
            client.expire(key, window_s)
        return n <= limit
    except Exception:  # pragma: no cover - never block on cache failure
        return True


def enforce(action: str, identifier: str, *, limit: int, window_s: int) -> None:
    if not allow(action, identifier, limit=limit, window_s=window_s):
        log.warning("rate_limited", action=action)
        raise RateLimited(f"Rate limit exceeded for {action}")
