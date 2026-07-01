"""Request helpers. Behind a proxy (Railway), request.client.host is the proxy's IP, so
per-IP rate limits and audit logs would collapse to a single value. When TRUST_PROXY is on
we take the client from X-Forwarded-For instead."""
from __future__ import annotations

from starlette.requests import Request

from leadpilot.common.config import settings


def client_ip(request: Request) -> str:
    """Best-effort real client IP. With TRUST_PROXY, use the first X-Forwarded-For hop
    (the original client per the de-facto convention); otherwise the socket peer."""
    if settings.trust_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
    return request.client.host if request.client else "unknown"
