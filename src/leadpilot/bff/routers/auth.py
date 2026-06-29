"""Auth: phone OTP → JWT (PRD §6.1.1, §9.1).

v1 uses a mock OTP (MOCK_OTP=true accepts a fixed dev code) so the dashboard can
authenticate without an SMS provider. Real MSG91/Twilio + auth_otps land in Phase 2.
"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from leadpilot.bff.schemas import (
    AccessOut,
    OtpRequest,
    OtpVerify,
    RefreshRequest,
    TokenOut,
    UserOut,
)
from leadpilot.common.auth import decode_token, issue_access_token, issue_refresh_token
from leadpilot.common.config import settings
from leadpilot.common.errors import AuthError, NotFoundError
from leadpilot.common.logging import get_logger
from leadpilot.core.db import platform_session
from leadpilot.core.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("auth")

DEV_OTP_CODE = "000000"


@router.post("/otp/request", status_code=202)
def otp_request(req: OtpRequest) -> dict:
    # Mock: pretend to send. Real path: MSG91 send + persist auth_otps with code_hash.
    log.info("otp_requested", phone=req.phone)
    resp = {"status": "sent"}
    if settings.mock_otp and not settings.is_production:
        resp["dev_code"] = DEV_OTP_CODE
    return resp


def _user_by_phone(phone: str) -> User | None:
    # users is the identity table (not RLS); safe to look up pre-tenant by phone.
    with platform_session() as session:
        return session.scalar(select(User).where(User.phone == phone))


@router.post("/otp/verify", response_model=TokenOut)
def otp_verify(req: OtpVerify) -> TokenOut:
    if settings.mock_otp:
        if req.code != DEV_OTP_CODE:
            raise AuthError("Invalid code", user_message_key="error.validation")
    else:  # pragma: no cover - real OTP in Phase 2
        raise AuthError("OTP provider not configured")

    user = _user_by_phone(req.phone)
    if user is None:
        raise NotFoundError("No account for this number")

    access = issue_access_token(
        user_id=str(user.id), tenant_id=str(user.tenant_id),
        account_id=str(user.account_id) if user.account_id else None, role=user.role,
    )
    refresh = issue_refresh_token(user_id=str(user.id), tenant_id=str(user.tenant_id))
    return TokenOut(
        access=access,
        refresh=refresh,
        user=UserOut(id=user.id, name=user.name, role=user.role,
                     account_id=user.account_id, locale=user.locale),
    )


@router.post("/refresh", response_model=AccessOut)
def refresh_token(req: RefreshRequest) -> AccessOut:
    try:
        claims = decode_token(req.refresh)
    except Exception as exc:  # noqa: BLE001
        raise AuthError("Invalid refresh token") from exc
    if claims.get("type") != "refresh":
        raise AuthError("Wrong token type")
    user = None
    with platform_session() as session:
        user = session.get(User, claims["sub"])
    if user is None:
        raise AuthError("Unknown user")
    access = issue_access_token(
        user_id=str(user.id), tenant_id=str(user.tenant_id),
        account_id=str(user.account_id) if user.account_id else None, role=user.role,
    )
    return AccessOut(access=access)
