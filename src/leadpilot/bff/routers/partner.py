"""Partner / agency console (PRD §6.10) — manage many clients from one screen.

A PARTNER tenant owns N sub-accounts. Endpoints operate within the partner's tenant
(RLS keeps them isolated from other partners), with per-client status + CPQL and a rollup.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from leadpilot.bff.deps import Principal, current_principal, require_role
from leadpilot.common.auth import issue_access_token
from leadpilot.common.errors import NotFoundError
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.enums import AccountPhase
from leadpilot.core.models import Account, AdInsight, BusinessProfile, Lead, Subscription, User
from leadpilot.core.money import format_paise

router = APIRouter(prefix="/partner", tags=["partner"])


class SubAccountIn(BaseModel):
    business_name: str
    category: str
    city: str = ""
    daily_budget_paise: int = 50000
    language: str = "hi"


@router.post("/sub-accounts")
def create_sub_account(body: SubAccountIn, principal: Principal = Depends(current_principal)) -> dict:
    require_role(principal, {"PARTNER", "ADMIN"})
    with tenant_session(principal.tenant_id) as s:
        acc = Account(tenant_id=principal.tenant_id, business_name=body.business_name,
                      category=body.category, default_language=body.language,
                      phase=AccountPhase.SIGNED_UP.value, created_via="partner")
        s.add(acc)
        s.flush()
        s.add(BusinessProfile(tenant_id=principal.tenant_id, account_id=acc.id,
                              service_area_city=body.city, daily_budget_paise=body.daily_budget_paise))
        return {"account_id": str(acc.id), "business_name": acc.business_name}


def _latest_cpql(s, account_id) -> int | None:
    row = s.scalar(
        select(AdInsight.cpql_paise).where(AdInsight.account_id == account_id)
        .order_by(AdInsight.date.desc())
    )
    return int(row) if row else None


@router.get("/sub-accounts")
def list_sub_accounts(principal: Principal = Depends(current_principal)) -> list[dict]:
    require_role(principal, {"PARTNER", "ADMIN"})
    today = datetime.now(UTC) - timedelta(days=1)
    with tenant_session(principal.tenant_id) as s:
        accounts = s.scalars(select(Account)).all()
        out = []
        for a in accounts:
            qualified = s.scalar(
                select(func.count(Lead.id)).where(
                    Lead.account_id == a.id, Lead.created_at >= today,
                    Lead.status.in_(["QUALIFIED_HOT", "QUALIFIED_WARM"]))
            ) or 0
            out.append({"account_id": str(a.id), "business_name": a.business_name,
                        "category": a.category, "phase": a.phase,
                        "qualified_24h": int(qualified), "cpql_paise": _latest_cpql(s, a.id)})
        return out


@router.get("/sub-accounts/{account_id}")
def sub_account_detail(
    account_id: str, principal: Principal = Depends(current_principal)
) -> dict:
    """One client's performance + billing at a glance. RLS confines the lookup to the
    partner's own tenant, so a partner can never see another agency's client."""
    require_role(principal, {"PARTNER", "ADMIN"})
    with tenant_session(principal.tenant_id) as s:
        a = s.get(Account, account_id)
        if a is None:
            raise NotFoundError("Client not found")
        profile = s.scalar(
            select(BusinessProfile).where(BusinessProfile.account_id == a.id)
        )
        spend = int(s.scalar(
            select(func.coalesce(func.sum(AdInsight.spend_paise), 0))
            .where(AdInsight.account_id == a.id)
        ) or 0)
        qualified = int(s.scalar(
            select(func.count(Lead.id)).where(
                Lead.account_id == a.id,
                Lead.status.in_(["QUALIFIED_HOT", "QUALIFIED_WARM"]))
        ) or 0)
        total_leads = int(s.scalar(
            select(func.count(Lead.id)).where(Lead.account_id == a.id)
        ) or 0)
        sub = s.scalar(select(Subscription).where(Subscription.account_id == a.id))
        # A simple 15% agency commission on managed spend, shown to the reseller.
        commission = (spend * 15) // 100
        return {
            "account_id": str(a.id),
            "business_name": a.business_name,
            "category": a.category,
            "phase": a.phase,
            "city": profile.service_area_city if profile else None,
            "daily_budget_paise": profile.daily_budget_paise if profile else 0,
            "total_spend_paise": spend,
            "total_spend_display": format_paise(spend),
            "total_leads": total_leads,
            "qualified_leads": qualified,
            "cpql_paise": _latest_cpql(s, a.id),
            "subscription_tier": sub.tier if sub else None,
            "subscription_status": sub.status if sub else None,
            "commission_paise": commission,
            "commission_display": format_paise(commission),
        }


@router.post("/sub-accounts/{account_id}/open")
def open_sub_account(
    account_id: str, principal: Principal = Depends(current_principal)
) -> dict:
    """Issue a short-lived owner-scoped token for one client so the partner can open that
    client's dashboard/leads/reports. Scoped to a single account in the partner's tenant."""
    require_role(principal, {"PARTNER", "ADMIN"})
    with tenant_session(principal.tenant_id) as s:
        a = s.get(Account, account_id)
        if a is None:
            raise NotFoundError("Client not found")
    # The token's subject stays the partner user (audited), so re-bind it to their live
    # token_version.
    with platform_session() as s:
        actor = s.get(User, principal.user_id)
        tv = actor.token_version if actor else 0
    token = issue_access_token(
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        account_id=account_id,
        role="OWNER",  # act as the client owner, but only for this one account
        token_version=tv,
    )
    return {"access": token, "account_id": account_id, "business_name": a.business_name}


@router.get("/rollup")
def rollup(principal: Principal = Depends(current_principal)) -> dict:
    require_role(principal, {"PARTNER", "ADMIN"})
    with tenant_session(principal.tenant_id) as s:
        n_accounts = s.scalar(select(func.count(Account.id))) or 0
        n_live = s.scalar(
            select(func.count(Account.id)).where(Account.phase.in_(["LIVE", "OPTIMIZING"]))
        ) or 0
        spend = s.scalar(select(func.coalesce(func.sum(AdInsight.spend_paise), 0))) or 0
        qualified = s.scalar(
            select(func.count(Lead.id)).where(Lead.status.in_(["QUALIFIED_HOT", "QUALIFIED_WARM"]))
        ) or 0
        avg_cpql = (spend // qualified) if qualified else None
        return {"accounts": int(n_accounts), "live": int(n_live),
                "total_spend_paise": int(spend), "qualified_leads": int(qualified),
                "avg_cpql_paise": avg_cpql}
