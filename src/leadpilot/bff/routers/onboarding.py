"""Onboarding: business profile + connections + status (PRD §6.1, §9.1).

v1 updates the authenticated owner's account/profile and kicks off Scout research.
Meta Embedded Signup / WhatsApp Embedded Signup callbacks are stubbed for Phase 2
(they persist meta_connections / whatsapp_connections when real onboarding is wired).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from leadpilot.bff.deps import Principal, current_principal
from leadpilot.common.config import settings
from leadpilot.common.crypto import encrypt
from leadpilot.common.errors import NotFoundError, ValidationError
from leadpilot.common.i18n import normalize_locale
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.enums import AccountPhase, WhatsAppMode
from leadpilot.core.models import (
    Account,
    BusinessProfile,
    MetaConnection,
    WaRoute,
    WhatsAppConnection,
)
from leadpilot.saathi.ad_styles import is_valid_style, styles_for_locale

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class BusinessIn(BaseModel):
    business_name: str
    category: str
    offer: str
    city: str
    radius_km: int = 10
    daily_budget_paise: int = 50000
    # THE goal: the most the owner would pay for one lead. Everything downstream
    # (kill rules, scaling, reports) optimizes toward this number.
    target_cpql_paise: int | None = None
    language: str = "hi"
    # "What kind of ad" — one of ad_styles.AD_STYLES, or "auto"/None to let Saathi decide.
    ad_style: str | None = None


class StatusOut(BaseModel):
    phase: str
    missing_steps: list[str]


class WhatsAppConnectIn(BaseModel):
    # APP_DESTINATION = fastest go-live (CTWA → owner's own WhatsApp app, no API).
    # CLOUD_API / BSP = the AI Closer runs on inbound webhooks.
    mode: str = "APP_DESTINATION"
    phone: str | None = None             # owner's WhatsApp number (APP_DESTINATION)
    waba_id: str | None = None
    phone_number_id: str | None = None   # routing key for CLOUD_API/BSP


class MetaConnectIn(BaseModel):
    meta_business_id: str
    ad_account_id: str
    page_id: str
    system_user_token: str | None = None


class EmbeddedSignupIn(BaseModel):
    code: str                       # OAuth code from Meta Embedded Signup
    ad_account_id: str
    page_id: str
    meta_business_id: str | None = None


@router.post("/business")
def set_business(body: BusinessIn, principal: Principal = Depends(current_principal)) -> dict:
    if not principal.account_id:
        raise NotFoundError("No account for this user")
    with tenant_session(principal.tenant_id) as s:
        account = s.get(Account, principal.account_id)
        if account is None:
            raise NotFoundError("Account not found")
        account.business_name = body.business_name
        account.category = body.category
        account.default_language = normalize_locale(body.language)
        if body.target_cpql_paise:
            account.target_cpql_paise = body.target_cpql_paise
        # "auto"/blank means let Saathi decide → store NULL; a real key must be valid.
        style = None if body.ad_style in (None, "", "auto") else body.ad_style
        if not is_valid_style(style):
            raise ValidationError(f"Unknown ad style: {body.ad_style}")
        account.ad_style = style
        if account.phase == AccountPhase.SIGNED_UP.value:
            account.phase = AccountPhase.ONBOARDING.value

        profile = s.scalar(
            select(BusinessProfile).where(BusinessProfile.account_id == account.id)
        )
        if profile is None:
            profile = BusinessProfile(tenant_id=principal.tenant_id, account_id=account.id)
            s.add(profile)
        profile.offer = body.offer
        profile.service_area_city = body.city
        profile.service_radius_km = body.radius_km
        profile.daily_budget_paise = body.daily_budget_paise
        return {"account_id": str(account.id), "phase": account.phase}


@router.get("/ad-styles")
def ad_styles(
    locale: str | None = None, principal: Principal = Depends(current_principal)
) -> dict:
    """Owner-facing ad-style choices ('what kind of ad?'), with the current selection.
    'auto' is first and recommended. Labels use ?locale if given (so the onboarding picker
    matches the UI the owner just chose), else the account's saved language."""
    acct_locale = "en"
    selected = "auto"
    if principal.account_id:
        with tenant_session(principal.tenant_id) as s:
            account = s.get(Account, principal.account_id)
            if account:
                acct_locale = account.default_language
                selected = account.ad_style or "auto"
    return {"styles": styles_for_locale(locale or acct_locale), "selected": selected}


@router.post("/whatsapp/connect")
def connect_whatsapp(body: WhatsAppConnectIn, principal: Principal = Depends(current_principal)) -> dict:
    mode = body.mode.upper()
    if mode not in {m.value for m in WhatsAppMode}:
        raise ValidationError(f"Unknown WhatsApp mode: {mode}")
    if not principal.account_id:
        raise NotFoundError("No account")
    if mode in (WhatsAppMode.APP_DESTINATION.value, WhatsAppMode.CALL.value) \
            and not body.phone:
        raise ValidationError("phone is required for APP_DESTINATION/CALL")
    if mode == WhatsAppMode.CLOUD_API.value and not body.phone_number_id:
        raise ValidationError("phone_number_id is required for CLOUD_API")

    with tenant_session(principal.tenant_id) as s:
        conn = s.scalar(
            select(WhatsAppConnection).where(WhatsAppConnection.account_id == principal.account_id)
        )
        if conn is None:
            conn = WhatsAppConnection(tenant_id=principal.tenant_id, account_id=principal.account_id)
            s.add(conn)
        conn.mode = mode
        conn.waba_id = body.waba_id
        conn.phone_number_id = body.phone_number_id
        conn.display_phone = body.phone

    # CLOUD_API/BSP: register the routing key so inbound webhooks resolve the tenant.
    if mode != WhatsAppMode.APP_DESTINATION.value and body.phone_number_id:
        with platform_session() as s:
            existing = s.scalar(
                select(WaRoute).where(WaRoute.phone_number_id == body.phone_number_id))
            if existing is None:
                s.add(WaRoute(phone_number_id=body.phone_number_id,
                              tenant_id=principal.tenant_id, account_id=principal.account_id))
            elif str(existing.tenant_id) == str(principal.tenant_id):
                # Recycled/reassigned within the same tenant — safe to re-point.
                existing.account_id = principal.account_id
            else:
                # A phone_number_id already owned by ANOTHER tenant must not be silently
                # hijacked (it would route their leads to us). Fail closed; ops must
                # verify + release it first.
                raise ValidationError(
                    "This WhatsApp number is already registered to another account. "
                    "Contact support to transfer it."
                )
    return {"mode": mode, "closer_enabled": mode != WhatsAppMode.APP_DESTINATION.value}


@router.post("/meta/connect")
def connect_meta(body: MetaConnectIn, principal: Principal = Depends(current_principal)) -> dict:
    """Store the Meta ad-account/Page connection. Token encrypted at rest."""
    if not principal.account_id:
        raise NotFoundError("No account")
    with tenant_session(principal.tenant_id) as s:
        conn = s.scalar(
            select(MetaConnection).where(MetaConnection.account_id == principal.account_id))
        if conn is None:
            conn = MetaConnection(tenant_id=principal.tenant_id, account_id=principal.account_id)
            s.add(conn)
        conn.meta_business_id = body.meta_business_id
        conn.ad_account_id = body.ad_account_id
        conn.page_id = body.page_id
        if body.system_user_token:
            conn.system_user_token_enc = encrypt(body.system_user_token)
        conn.status = "ACTIVE"
    return {"status": "connected", "ad_account_id": body.ad_account_id}


@router.get("/meta/embedded-signup/start")
def meta_embedded_signup_start(principal: Principal = Depends(current_principal)) -> dict:
    """Return the Meta Embedded-Signup OAuth dialog URL to open in a popup — the owner
    authorises once and we receive the ad-account/Page/token via the callback, so they
    never paste raw IDs. `configured=false` (no Meta app id) tells the UI to fall back to
    the manual connect fields for local/dev."""
    if not principal.account_id:
        raise NotFoundError("No account")
    configured = bool(settings.meta_app_id)
    redirect_uri = f"{settings.web_base_url}/onboarding/connect"
    scope = "ads_management,business_management,whatsapp_business_management,pages_show_list"
    url = (
        f"https://www.facebook.com/{settings.meta_graph_api_version}/dialog/oauth"
        f"?client_id={settings.meta_app_id or ''}"
        f"&redirect_uri={redirect_uri}"
        f"&state={principal.account_id}"
        f"&scope={scope}"
    ) if configured else ""
    return {"configured": configured, "url": url}


@router.post("/meta/embedded-signup/callback")
def meta_embedded_signup(body: EmbeddedSignupIn, principal: Principal = Depends(current_principal)) -> dict:
    """Exchange the Embedded-Signup OAuth code for a long-lived token (encrypted at rest).
    Removes manual token entry for self-serve onboarding (PRD §6.1.2)."""
    if not principal.account_id:
        raise NotFoundError("No account")
    token = _exchange_meta_code(body.code)
    with tenant_session(principal.tenant_id) as s:
        conn = s.scalar(
            select(MetaConnection).where(MetaConnection.account_id == principal.account_id))
        if conn is None:
            conn = MetaConnection(tenant_id=principal.tenant_id, account_id=principal.account_id)
            s.add(conn)
        conn.meta_business_id = body.meta_business_id
        conn.ad_account_id = body.ad_account_id
        conn.page_id = body.page_id
        conn.system_user_token_enc = encrypt(token)
        conn.status = "ACTIVE"
    return {"status": "connected", "ad_account_id": body.ad_account_id}


def _exchange_meta_code(code: str) -> str:
    """OAuth code → access token. Mocked unless real Meta creds are configured."""
    if settings.mock_meta or not settings.meta_app_secret:
        return f"mock-system-user-token-{code[:8]}"
    import httpx  # pragma: no cover - requires live creds

    resp = httpx.get(
        f"https://graph.facebook.com/{settings.meta_graph_api_version}/oauth/access_token",
        params={"client_id": settings.meta_app_id, "client_secret": settings.meta_app_secret,
                "code": code, "redirect_uri": f"{settings.app_base_url}/onboarding/meta/callback"},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@router.get("/status", response_model=StatusOut)
def status(principal: Principal = Depends(current_principal)) -> StatusOut:
    if not principal.account_id:
        raise NotFoundError("No account")
    with tenant_session(principal.tenant_id) as s:
        account = s.get(Account, principal.account_id)
        if account is None:
            raise NotFoundError("Account not found")
        missing: list[str] = []
        if not s.scalar(select(BusinessProfile).where(BusinessProfile.account_id == account.id)):
            missing.append("business_profile")
        if not s.scalar(select(MetaConnection).where(MetaConnection.account_id == account.id)):
            missing.append("meta_connection")
        if not s.scalar(select(WhatsAppConnection).where(WhatsAppConnection.account_id == account.id)):
            missing.append("whatsapp_connection")
        return StatusOut(phase=account.phase, missing_steps=missing)
