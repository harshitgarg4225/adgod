"""Owner self-service: edit business details/budget/language, control autopilot, and the
pause/resume kill-switch (PRD §6.7, §12 — trust). Everything here is owner-facing and
account-scoped; RLS confines writes to the owner's own tenant."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from leadpilot.bff.deps import Principal, current_principal, require_account_access
from leadpilot.common.clock import ist_month_start
from leadpilot.common.errors import NotFoundError, ValidationError
from leadpilot.common.i18n import SUPPORTED_LOCALES
from leadpilot.core.db import tenant_session
from leadpilot.core.enums import AccountPhase, AutopilotLevel
from leadpilot.core.models import Account, AdInsight, BusinessProfile, Subscription
from leadpilot.core.money import format_paise

router = APIRouter(tags=["settings"])

# Phases from which a pause is meaningful, and the phase we restore to on resume.
_RESUMABLE = {AccountPhase.LIVE.value, AccountPhase.OPTIMIZING.value,
              AccountPhase.FATIGUE_REFRESH.value}


class SettingsOut(BaseModel):
    business_name: str
    category: str
    offer: str | None
    service_area_city: str | None
    service_radius_km: int
    daily_budget_paise: int
    daily_budget_display: str
    target_cpql_paise: int
    target_cpql_display: str
    default_language: str
    autopilot_level: str
    auto_approve_hours: int
    phase: str
    paused: bool
    subscription_tier: str | None
    subscription_status: str | None
    gstin: str | None
    legal_name: str | None
    billing_address: str | None
    monthly_cap_paise: int | None
    monthly_spend_paise: int
    monthly_spend_display: str


class SettingsPatch(BaseModel):
    business_name: str | None = Field(default=None, max_length=200)
    offer: str | None = Field(default=None, max_length=2000)
    service_area_city: str | None = Field(default=None, max_length=80)
    service_radius_km: int | None = Field(default=None, ge=1, le=100)
    daily_budget_paise: int | None = Field(default=None, ge=10000)  # ≥ ₹100/day
    # Hard monthly spend ceiling (enforced at launch + optimizer); None/0 = uncapped.
    monthly_cap_paise: int | None = Field(default=None, ge=0)
    # The goal: max acceptable cost per qualified lead (₹20–₹5000).
    target_cpql_paise: int | None = Field(default=None, ge=2000, le=500000)
    default_language: str | None = None
    autopilot_level: str | None = None
    # 0 disables auto-launch (Saathi waits for the owner forever); 1-72 hours otherwise.
    auto_approve_hours: int | None = Field(default=None, ge=0, le=72)
    gstin: str | None = Field(default=None, max_length=20)
    legal_name: str | None = Field(default=None, max_length=200)
    billing_address: str | None = Field(default=None, max_length=1000)


def month_to_date_spend(session, account_id: str) -> int:
    """Sum of account-level ad spend since the 1st of the current month (IST — the
    business/billing day follows the ad account timezone, not UTC)."""
    month_start = ist_month_start()
    total = session.execute(
        select(func.coalesce(func.sum(AdInsight.spend_paise), 0)).where(
            AdInsight.account_id == account_id,
            AdInsight.level == "ACCOUNT",
            AdInsight.date >= month_start,
        )
    ).scalar_one()
    return int(total or 0)


def _load(session, account_id: str) -> tuple[Account, BusinessProfile | None, Subscription | None]:
    account = session.get(Account, account_id)
    if account is None:
        raise NotFoundError("Account not found")
    profile = session.scalar(
        select(BusinessProfile).where(BusinessProfile.account_id == account_id)
    )
    sub = session.scalar(select(Subscription).where(Subscription.account_id == account_id))
    return account, profile, sub


@router.get("/accounts/{account_id}/settings", response_model=SettingsOut)
def get_settings(account_id: str, principal: Principal = Depends(current_principal)) -> SettingsOut:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        account, profile, sub = _load(s, account_id)
        budget = profile.daily_budget_paise if profile else 0
        cap = profile.monthly_cap_paise if profile else None
        mtd = month_to_date_spend(s, account_id)
        return SettingsOut(
            business_name=account.business_name,
            category=account.category,
            offer=profile.offer if profile else None,
            service_area_city=profile.service_area_city if profile else None,
            service_radius_km=profile.service_radius_km if profile else 10,
            daily_budget_paise=budget,
            daily_budget_display=format_paise(budget),
            target_cpql_paise=account.target_cpql_paise or 20000,
            target_cpql_display=format_paise(account.target_cpql_paise or 20000),
            default_language=account.default_language,
            autopilot_level=account.autopilot_level,
            auto_approve_hours=account.auto_approve_hours,
            phase=account.phase,
            paused=account.phase == AccountPhase.PAUSED.value,
            subscription_tier=sub.tier if sub else None,
            subscription_status=sub.status if sub else None,
            gstin=account.gstin,
            legal_name=account.legal_name,
            billing_address=account.billing_address,
            monthly_cap_paise=cap,
            monthly_spend_paise=mtd,
            monthly_spend_display=format_paise(mtd),
        )


@router.patch("/accounts/{account_id}/settings", response_model=SettingsOut)
def update_settings(
    account_id: str, patch: SettingsPatch, principal: Principal = Depends(current_principal)
) -> SettingsOut:
    require_account_access(principal, account_id)
    if patch.default_language and patch.default_language not in SUPPORTED_LOCALES:
        raise ValidationError(f"Unsupported language: {patch.default_language}")
    if patch.autopilot_level and patch.autopilot_level not in {a.value for a in AutopilotLevel}:
        raise ValidationError(f"Invalid autopilot level: {patch.autopilot_level}")
    with tenant_session(principal.tenant_id) as s:
        account, profile, _ = _load(s, account_id)
        if patch.business_name is not None:
            account.business_name = patch.business_name
        if patch.default_language is not None:
            account.default_language = patch.default_language
        if patch.autopilot_level is not None:
            account.autopilot_level = patch.autopilot_level
        if patch.auto_approve_hours is not None:
            account.auto_approve_hours = patch.auto_approve_hours
        if patch.target_cpql_paise is not None:
            account.target_cpql_paise = patch.target_cpql_paise
        if patch.gstin is not None:
            account.gstin = patch.gstin
        if patch.legal_name is not None:
            account.legal_name = patch.legal_name
        if patch.billing_address is not None:
            account.billing_address = patch.billing_address
        if profile is None and (patch.offer or patch.service_area_city or patch.daily_budget_paise):
            profile = BusinessProfile(tenant_id=account.tenant_id, account_id=account.id)
            s.add(profile)
        if profile is not None:
            if patch.offer is not None:
                profile.offer = patch.offer
            if patch.service_area_city is not None:
                profile.service_area_city = patch.service_area_city
            if patch.service_radius_km is not None:
                profile.service_radius_km = patch.service_radius_km
            if patch.monthly_cap_paise is not None:
                profile.monthly_cap_paise = patch.monthly_cap_paise or None
            if patch.daily_budget_paise is not None:
                profile.daily_budget_paise = patch.daily_budget_paise
                # Push the new budget to the LIVE Meta ad sets right away — an owner
                # lowering spend must actually lower spend, not just a DB row.
                if account.phase in _RESUMABLE:
                    from leadpilot.saathi.pipeline import reconcile_budgets

                    reconcile_budgets(s, tenant_id=account.tenant_id, account_id=account.id)
    return get_settings(account_id, principal)


class PauseOut(BaseModel):
    phase: str
    paused: bool


@router.post("/accounts/{account_id}/pause", response_model=PauseOut)
def pause(account_id: str, principal: Principal = Depends(current_principal)) -> PauseOut:
    """Owner kill-switch: stop all ad spend immediately — ON META, not just our rows.
    Only meaningful for live phases; pre-launch there is nothing to pause and flipping
    the phase would wedge the launch pipeline."""
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        account = s.get(Account, account_id)
        if account is None:
            raise NotFoundError("Account not found")
        if account.phase not in _RESUMABLE:
            raise ValidationError("Your ads aren't live yet — there's nothing to pause.")
        from leadpilot.saathi.pipeline import set_live_state

        set_live_state(s, tenant_id=account.tenant_id, account_id=account.id,
                       pause=True, reason="owner")
        return PauseOut(phase=account.phase, paused=True)


@router.post("/accounts/{account_id}/resume", response_model=PauseOut)
def resume(account_id: str, principal: Principal = Depends(current_principal)) -> PauseOut:
    """Resume restores the pre-pause phase and reactivates the Meta campaign + any paused
    ad sets — the recovery path after owner/emergency/trial pauses."""
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        account = s.get(Account, account_id)
        if account is None:
            raise NotFoundError("Account not found")
        from leadpilot.saathi.pipeline import set_live_state

        set_live_state(s, tenant_id=account.tenant_id, account_id=account.id, pause=False)
        return PauseOut(phase=account.phase, paused=False)
