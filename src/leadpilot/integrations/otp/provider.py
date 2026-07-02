"""OTP SMS provider (MSG91). MOCK_OTP=true no-ops the send (the code is surfaced as
`dev_code` for local/test). Real provider sends via MSG91's OTP API."""
from __future__ import annotations

import httpx

from leadpilot.common.config import settings
from leadpilot.common.logging import get_logger

log = get_logger("otp")


class OtpProvider:
    def send(self, *, phone: str, code: str) -> None:
        raise NotImplementedError


class MockOtpProvider(OtpProvider):
    def send(self, *, phone: str, code: str) -> None:
        log.info("otp_send_mock", phone=phone)  # code intentionally not logged


class Msg91OtpProvider(OtpProvider):  # pragma: no cover - requires key
    def send(self, *, phone: str, code: str) -> None:
        # MSG91 SendOTP v5. template_id is a DLT-registered OTP template — mandatory for
        # SMS delivery in India; without it MSG91 accepts the call and delivers nothing.
        if not (settings.msg91_api_key and settings.msg91_template_id):
            raise RuntimeError(
                "MSG91 not configured: set MSG91_API_KEY and MSG91_TEMPLATE_ID "
                "(DLT-registered OTP template)"
            )
        resp = httpx.post(
            "https://control.msg91.com/api/v5/otp",
            params={"mobile": phone.lstrip("+"),
                    "template_id": settings.msg91_template_id,
                    "otp": code, "otp_length": len(code)},
            headers={"authkey": settings.msg91_api_key},
            timeout=10.0,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("type") != "success":
            # MSG91 signals failures inside a 200 body — surface them, never fail silently
            # (a client standing at their shop can't log in and nobody would know why).
            raise RuntimeError(f"MSG91 send failed: {body.get('message', body)}")
        log.info("otp_sent", phone=phone)


def get_otp_provider() -> OtpProvider:
    if settings.mock_otp:
        return MockOtpProvider()
    return Msg91OtpProvider()  # pragma: no cover
