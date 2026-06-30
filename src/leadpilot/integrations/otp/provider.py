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
        # MSG91 OTP/flow API; exact endpoint/fields per MSG91 docs at integration time.
        httpx.post(
            "https://control.msg91.com/api/v5/otp",
            params={"mobile": phone.lstrip("+"), "otp": code,
                    "authkey": settings.msg91_api_key},
            timeout=10.0,
        )


def get_otp_provider() -> OtpProvider:
    if settings.mock_otp:
        return MockOtpProvider()
    return Msg91OtpProvider()  # pragma: no cover
