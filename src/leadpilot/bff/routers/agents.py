"""Drive + inspect Saathi (PRD §9.2, §9.3).

v1 runs pipeline phases synchronously inside the request for a tight demo loop; in
production these endpoints enqueue worker jobs (the pipeline functions are identical
either way). All writes are tenant-scoped + access-checked.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from leadpilot.bff.deps import Principal, current_principal, require_account_access
from leadpilot.core.db import tenant_session
from leadpilot.core.models import (
    AdInsight,
    Angle,
    BusinessBrief,
    Campaign,
    Creative,
    OptimizationDecision,
)
from leadpilot.saathi import pipeline

router = APIRouter(tags=["saathi"])


@router.post("/accounts/{account_id}/research/run")
def research(account_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        brief_id = pipeline.run_research(s, tenant_id=principal.tenant_id, account_id=account_id)
    return {"brief_id": str(brief_id)}


@router.get("/accounts/{account_id}/brief")
def get_brief(account_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        b = s.scalar(
            select(BusinessBrief).where(BusinessBrief.account_id == account_id)
            .order_by(BusinessBrief.version.desc())
        )
        if b is None:
            return {}
        return {"id": str(b.id), "offer": b.offer, "audience": b.audience, "usp": b.usp,
                "objections": b.objections, "tone": b.tone, "version": b.version}


@router.get("/accounts/{account_id}/angles")
def get_angles(account_id: str, principal: Principal = Depends(current_principal)) -> list[dict]:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        rows = s.scalars(select(Angle).where(Angle.account_id == account_id)).all()
        return [{"id": str(a.id), "title": a.title, "rationale": a.rationale,
                 "hypothesis": a.hypothesis, "status": a.status} for a in rows]


@router.post("/accounts/{account_id}/creatives/generate")
def gen_creatives(account_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        ids = pipeline.run_creative(s, tenant_id=principal.tenant_id, account_id=account_id)
    return {"creative_ids": [str(i) for i in ids]}


@router.get("/accounts/{account_id}/creatives")
def list_creatives(account_id: str, principal: Principal = Depends(current_principal)) -> list[dict]:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        rows = s.scalars(select(Creative).where(Creative.account_id == account_id)).all()
        return [{"id": str(c.id), "headline": c.headline, "primary_text": c.primary_text,
                 "asset_url": c.asset_url, "compliance_status": c.compliance_status,
                 "approval_status": c.approval_status, "language": c.language} for c in rows]


@router.post("/creatives/{creative_id}/approve")
def approve_creative(creative_id: str, principal: Principal = Depends(current_principal)) -> dict:
    with tenant_session(principal.tenant_id) as s:
        c = s.get(Creative, creative_id)
        if c is None:
            return {"ok": False}
        require_account_access(principal, str(c.account_id))
        c.approval_status = "APPROVED_FOR_LAUNCH"
        return {"ok": True, "id": creative_id}


@router.post("/accounts/{account_id}/campaigns/launch")
def launch(account_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        ids = pipeline.launch_campaigns(s, tenant_id=principal.tenant_id, account_id=account_id)
    return {"campaign_ids": [str(i) for i in ids]}


@router.get("/accounts/{account_id}/campaigns")
def list_campaigns(account_id: str, principal: Principal = Depends(current_principal)) -> list[dict]:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        rows = s.scalars(select(Campaign).where(Campaign.account_id == account_id)).all()
        # Owner-simple view (PRD §6.4.3): status + budget only, no Ads-Manager complexity.
        return [{"id": str(c.id), "status": c.status, "channel": c.channel,
                 "daily_budget_paise": c.daily_budget_paise} for c in rows]


@router.post("/accounts/{account_id}/optimize/run")
def optimize(account_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        decisions = pipeline.run_optimization(s, tenant_id=principal.tenant_id, account_id=account_id)
    return {"decisions": decisions}


@router.get("/accounts/{account_id}/optimization/decisions")
def list_decisions(account_id: str, principal: Principal = Depends(current_principal)) -> list[dict]:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        rows = s.scalars(
            select(OptimizationDecision).where(OptimizationDecision.account_id == account_id)
            .order_by(OptimizationDecision.created_at.desc())
        ).all()
        return [{"action": d.action, "reason_code": d.reason_code, "level": d.level,
                 "applied": d.applied} for d in rows]


@router.get("/accounts/{account_id}/insights")
def insights(
    account_id: str, limit: int = Query(default=50, le=200),
    principal: Principal = Depends(current_principal),
) -> list[dict]:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        rows = s.scalars(
            select(AdInsight).where(AdInsight.account_id == account_id)
            .order_by(AdInsight.date.desc()).limit(limit)
        ).all()
        return [{"level": r.level, "spend_paise": r.spend_paise, "impressions": r.impressions,
                 "clicks": r.clicks, "ctr": r.ctr, "frequency": r.frequency, "leads": r.leads,
                 "cpl_paise": r.cpl_paise, "cpql_paise": r.cpql_paise} for r in rows]


@router.post("/accounts/{account_id}/report/run")
def report(account_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        msg = pipeline.run_report(s, tenant_id=principal.tenant_id, account_id=account_id)
    return {"message": msg}
