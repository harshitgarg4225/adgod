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
from leadpilot.common.errors import NotFoundError
from leadpilot.common.i18n import normalize_locale
from leadpilot.core.db import tenant_session
from leadpilot.core.enums import AccountPhase
from leadpilot.core.models import Account, BusinessProfile, MetaConnection, WhatsAppConnection

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class BusinessIn(BaseModel):
    business_name: str
    category: str
    offer: str
    city: str
    radius_km: int = 10
    daily_budget_paise: int = 50000
    language: str = "hi"


class StatusOut(BaseModel):
    phase: str
    missing_steps: list[str]


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
