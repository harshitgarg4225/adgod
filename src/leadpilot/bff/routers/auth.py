"""Auth: phone OTP → JWT (PRD §6.1.1, §9.1).

Real OTP: a 6-digit code is generated, its hash + expiry stored in auth_otps, and sent
via the OTP provider (MSG91). Verification checks the stored hash. With MOCK_OTP=true the
send is a no-op and the code is returned as `dev_code` for local/test use.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

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
from leadpilot.core.models import AuthOtp, User
from leadpilot.integrations.otp import get_otp_provider

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("auth")

OTP_TTL_MIN = 5


def _hash(code: str) -> str:
    return hashlib.sha256(f"{settings.jwt_secret}:{code}".encode()).hexdigest()


@router.post("/otp/request", status_code=202)
def otp_request(req: OtpRequest) -> dict:
    code = f"{secrets.randbelow(1_000_000):06d}"
    with platform_session() as s:
        s.add(AuthOtp(phone=req.phone, code_hash=_hash(code),
                      expires_at=datetime.now(UTC) + timedelta(minutes=OTP_TTL_MIN)))
    get_otp_provider().send(phone=req.phone, code=code)
    log.info("otp_requested", phone=req.phone)
    resp = {"status": "sent"}
    if settings.mock_otp and not settings.is_production:
        resp["dev_code"] = code  # surfaced only in non-prod mock mode
    return resp


def _user_by_phone(phone: str) -> User | None:
    with platform_session() as s:
        return s.scalar(select(User).where(User.phone == phone))


@router.post("/otp/verify", response_model=TokenOut)
def otp_verify(req: OtpVerify) -> TokenOut:
    now = datetime.now(UTC)
    with platform_session() as s:
        otp = s.scalar(
            select(AuthOtp).where(AuthOtp.phone == req.phone, AuthOtp.consumed_at.is_(None),
                                  AuthOtp.expires_at > now)
            .order_by(AuthOtp.created_at.desc())
        )
        if otp is None or otp.code_hash != _hash(req.code):
            raise AuthError("Invalid or expired code", user_message_key="error.validation")
        otp.consumed_at = now

    user = _user_by_phone(req.phone)
    if user is None:
        raise NotFoundError("No account for this number")

    access = issue_access_token(
        user_id=str(user.id), tenant_id=str(user.tenant_id),
        account_id=str(user.account_id) if user.account_id else None, role=user.role,
    )
    refresh = issue_refresh_token(user_id=str(user.id), tenant_id=str(user.tenant_id))
    return TokenOut(
        access=access, refresh=refresh,
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
    with platform_session() as s:
        user = s.get(User, claims["sub"])
    if user is None:
        raise AuthError("Unknown user")
    access = issue_access_token(
        user_id=str(user.id), tenant_id=str(user.tenant_id),
        account_id=str(user.account_id) if user.account_id else None, role=user.role,
    )
    return AccessOut(access=access)
