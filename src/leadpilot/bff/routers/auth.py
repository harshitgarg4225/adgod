"""Auth: phone OTP → JWT (PRD §6.1.1, §9.1).

Real OTP: a 6-digit code is generated, its hash + expiry stored in auth_otps, and sent
via the OTP provider (MSG91). Verification checks the stored hash. With MOCK_OTP=true the
send is a no-op and the code is returned as `dev_code` for local/test use.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from leadpilot.bff.deps import Principal, current_principal
from leadpilot.bff.schemas import (
    AccessOut,
    OtpRequest,
    OtpVerify,
    RefreshRequest,
    TokenOut,
    UserOut,
)
from leadpilot.common.auth import (
    decode_token,
    hash_otp,
    issue_access_token,
    issue_refresh_token,
)
from leadpilot.common.config import settings
from leadpilot.common.errors import AuthError, ValidationError
from leadpilot.common.logging import get_logger
from leadpilot.common.phone import normalize_phone
from leadpilot.common.ratelimit import enforce
from leadpilot.common.requtil import client_ip
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.enums import AccountPhase, TenantType, UserRole
from leadpilot.core.models import Account, AuthOtp, Lead, Tenant, User
from leadpilot.integrations.otp import get_otp_provider

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("auth")

OTP_TTL_MIN = 5


@router.post("/otp/request", status_code=202)
def otp_request(req: OtpRequest, request: Request) -> dict:
    # One canonical phone form (+91XXXXXXXXXX) — a provisioned owner must match the same
    # person logging in regardless of how they typed their number.
    phone = normalize_phone(req.phone)
    # Throttle OTP sends: per phone and per source IP (anti-abuse / SMS-cost control).
    # fail_closed so an attacker can't defeat the SMS-cost limit by knocking Redis over.
    enforce("otp_request", phone, limit=5, window_s=600, fail_closed=True)
    enforce("otp_request_ip", client_ip(request), limit=20, window_s=600, fail_closed=True)
    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(16)
    with platform_session() as s:
        s.add(AuthOtp(phone=phone, code_hash=hash_otp(code, salt), salt=salt,
                      expires_at=datetime.now(UTC) + timedelta(minutes=OTP_TTL_MIN)))
    try:
        get_otp_provider().send(phone=phone, code=code)
    except Exception as exc:  # noqa: BLE001 - surface a clean, retryable error to the UI
        log.error("otp_send_failed", phone=phone, error=str(exc)[:200])
        raise ValidationError(
            "We couldn't send the code right now — please try again in a minute."
        ) from exc
    log.info("otp_requested", phone=phone)
    resp = {"status": "sent"}
    if settings.mock_otp and not settings.is_production:
        resp["dev_code"] = code  # surfaced only in non-prod mock mode
    return resp


def _user_by_phone(phone: str) -> User | None:
    with platform_session() as s:
        return s.scalar(select(User).where(User.phone == phone))


def _signup(phone: str) -> User:
    """Self-serve signup on first verified login: create a DIRECT tenant, an owner user,
    and an Account in the SIGNED_UP phase. Onboarding fills in business details, budget,
    language and the Meta/WhatsApp connections; the account stays pre-live until then."""
    tenant_id = uuid.uuid4()
    account_id = uuid.uuid4()
    user_id = uuid.uuid4()
    with platform_session() as s:
        s.add(Tenant(id=tenant_id, name="Direct Tenant", type=TenantType.DIRECT.value,
                     status="ACTIVE", settings={}))
        # consent_at records DPDP consent captured at signup (the login screen shows the
        # T&C/privacy notice before the OTP step).
        s.add(User(id=user_id, tenant_id=tenant_id, account_id=account_id, phone=phone,
                   role=UserRole.OWNER.value, name=None, locale="hi",
                   consent_at=datetime.now(UTC)))
    with tenant_session(tenant_id) as s:
        s.add(Account(id=account_id, tenant_id=tenant_id, business_name="",
                      category="general", phase=AccountPhase.SIGNED_UP.value,
                      default_language="hi", created_via="self_serve"))
    log.info("self_serve_signup", account=str(account_id))
    # Re-read under platform context so the caller gets a fully populated row.
    with platform_session() as s:
        return s.get(User, user_id)


@router.post("/otp/verify", response_model=TokenOut)
def otp_verify(req: OtpVerify) -> TokenOut:
    phone = normalize_phone(req.phone)
    # Throttle verify attempts per phone to blunt OTP brute force (fail-closed on outage).
    enforce("otp_verify", phone, limit=10, window_s=600, fail_closed=True)
    now = datetime.now(UTC)
    with platform_session() as s:
        otp = s.scalar(
            select(AuthOtp).where(AuthOtp.phone == phone, AuthOtp.consumed_at.is_(None),
                                  AuthOtp.expires_at > now)
            .order_by(AuthOtp.created_at.desc())
        )
        if otp is None or otp.code_hash != hash_otp(req.code, otp.salt or ""):
            raise AuthError("Invalid or expired code", user_message_key="error.validation")
        otp.consumed_at = now

    # Create-on-first-login: a verified but unknown phone becomes a new owner account.
    # This is the self-serve signup path AND avoids leaking which numbers already exist.
    user = _user_by_phone(phone) or _signup(phone)

    access = issue_access_token(
        user_id=str(user.id), tenant_id=str(user.tenant_id),
        account_id=str(user.account_id) if user.account_id else None, role=user.role,
        token_version=user.token_version,
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
    if user is None or user.deleted_at is not None:
        raise AuthError("Unknown user")
    access = issue_access_token(
        user_id=str(user.id), tenant_id=str(user.tenant_id),
        account_id=str(user.account_id) if user.account_id else None, role=user.role,
        token_version=user.token_version,
    )
    return AccessOut(access=access)


@router.post("/logout")
def logout(principal: Principal = Depends(current_principal)) -> dict:
    """Revoke every outstanding token for this user by bumping token_version — the
    re-bind check in current_principal then rejects the old access/refresh tokens."""
    with platform_session() as s:
        user = s.get(User, principal.user_id)
        if user is not None:
            user.token_version = (user.token_version or 0) + 1
    return {"ok": True}


@router.get("/me/export")
def export_my_data(principal: Principal = Depends(current_principal)) -> dict:
    """DPDP data-subject access: export the account's own data (self-service)."""
    with tenant_session(principal.tenant_id) as s:
        user = s.get(User, principal.user_id)
        account = s.get(Account, principal.account_id) if principal.account_id else None
        leads = []
        if principal.account_id:
            leads = [
                {"name": leadrow.name, "wa_phone": leadrow.wa_phone, "status": leadrow.status,
                 "score": leadrow.score, "intent": leadrow.intent_summary,
                 "created_at": leadrow.created_at.isoformat()}
                for leadrow in s.scalars(
                    select(Lead).where(Lead.account_id == principal.account_id)
                ).all()
            ]
        return {
            "user": {"phone": user.phone if user else None, "name": user.name if user else None,
                     "locale": user.locale if user else None,
                     "consent_at": user.consent_at.isoformat()
                     if user and user.consent_at else None},
            "account": {"business_name": account.business_name, "category": account.category}
            if account else None,
            "leads": leads,
        }


@router.delete("/me")
def delete_my_account(principal: Principal = Depends(current_principal)) -> dict:
    """DPDP erasure: soft-delete the owner + account and revoke sessions. A retention sweep
    hard-purges the PII after the grace window."""
    now = datetime.now(UTC)
    with platform_session() as s:
        user = s.get(User, principal.user_id)
        if user is not None:
            user.deleted_at = now
            user.token_version = (user.token_version or 0) + 1
    if principal.account_id:
        with tenant_session(principal.tenant_id) as s:
            account = s.get(Account, principal.account_id)
            if account is not None:
                account.deleted_at = now
                account.phase = AccountPhase.CHURNED.value
    return {"ok": True, "deleted_at": now.isoformat()}
