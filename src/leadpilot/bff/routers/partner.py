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
from leadpilot.core.db import tenant_session
from leadpilot.core.enums import AccountPhase
from leadpilot.core.models import Account, AdInsight, BusinessProfile, Lead

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
