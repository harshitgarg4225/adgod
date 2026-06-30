"""Baseline security response headers for the FastAPI services.

Applied to every response on both the BFF and webhook-intake apps. These are cheap,
defence-in-depth headers (clickjacking, MIME-sniffing, referrer leakage, HSTS). The CSP
is intentionally strict for the API surface — it serves JSON, not HTML — while the Next.js
app sets its own CSP for the rendered UI.
"""
from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from leadpilot.common.config import settings

_HEADERS = {
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"referrer-policy": b"no-referrer",
    b"cross-origin-opener-policy": b"same-origin",
    b"content-security-policy": b"default-src 'none'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware:
    """Pure-ASGI middleware so it runs for every response, including errors."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                existing = {k.lower() for k, _ in headers}
                for key, value in _HEADERS.items():
                    if key not in existing:
                        headers.append((key, value))
                # HSTS only over TLS / in production to avoid pinning HTTP during local dev.
                if settings.is_production and b"strict-transport-security" not in existing:
                    headers.append(
                        (b"strict-transport-security",
                         b"max-age=31536000; includeSubDomains")
                    )
            await send(message)

        await self.app(scope, receive, send_wrapper)
