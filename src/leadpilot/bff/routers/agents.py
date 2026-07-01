"""Drive + inspect Saathi (PRD §9.2, §9.3).

v1 runs pipeline phases synchronously inside the request for a tight demo loop; in
production these endpoints enqueue worker jobs (the pipeline functions are identical
either way). All writes are tenant-scoped + access-checked.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select

from leadpilot.bff.deps import Principal, current_principal, require_account_access
from leadpilot.bff.routers.settings import month_to_date_spend
from leadpilot.common.config import settings
from leadpilot.common.errors import NotFoundError, ValidationError
from leadpilot.core.db import tenant_session
from leadpilot.core.models import (
    AdInsight,
    Angle,
    Approval,
    BusinessBrief,
    BusinessProfile,
    Campaign,
    Creative,
    OptimizationDecision,
)
from leadpilot.saathi import pipeline
from leadpilot.saathi.guardrails.spend import check_monthly_cap
from leadpilot.worker.dispatch import enqueue_pipeline

router = APIRouter(tags=["saathi"])

# Map each owner-initiated phase to its worker task (used when pipeline_inline=false).
_PHASE_TASKS = {
    "research": ("leadpilot.pipeline.research", "agent"),
    "creative": ("leadpilot.pipeline.creative", "agent"),
    "launch": ("leadpilot.launch.run", "launch"),
    "optimize": ("leadpilot.optimizer.run", "optimizer"),
    "report": ("leadpilot.reporter.run", "agent"),
}


def _maybe_enqueue(phase: str, tenant_id: str, account_id: str) -> dict | None:
    """In production (pipeline_inline=false) enqueue the phase and return a 'queued' dict;
    inline (pilot/dev) returns None so the caller runs it synchronously."""
    if settings.pipeline_inline:
        return None
    task, queue = _PHASE_TASKS[phase]
    enqueue_pipeline(task, tenant_id, account_id, queue=queue)
    return {"status": "queued", "phase": phase}


@router.post("/accounts/{account_id}/research/run")
def research(account_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require_account_access(principal, account_id)
    if (q := _maybe_enqueue("research", principal.tenant_id, account_id)):
        return q
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
    if (q := _maybe_enqueue("creative", principal.tenant_id, account_id)):
        return q
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


@router.post("/creatives/{creative_id}/reject")
def reject_creative(creative_id: str, principal: Principal = Depends(current_principal)) -> dict:
    """Owner rejects a creative — it won't launch. Regenerate the batch to get fresh ones."""
    with tenant_session(principal.tenant_id) as s:
        c = s.get(Creative, creative_id)
        if c is None:
            return {"ok": False}
        require_account_access(principal, str(c.account_id))
        c.approval_status = "REJECTED"
        return {"ok": True, "id": creative_id}


class BriefPatch(BaseModel):
    offer: str | None = None
    audience: list[str] | None = None
    usp: list[str] | None = None
    objections: list[str] | None = None
    tone: str | None = None


@router.patch("/accounts/{account_id}/brief")
def update_brief(
    account_id: str, patch: BriefPatch, principal: Principal = Depends(current_principal)
) -> dict:
    """Owner corrects Saathi's understanding before ads are written (a wrong brief poisons
    every downstream creative)."""
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        b = s.scalar(
            select(BusinessBrief).where(BusinessBrief.account_id == account_id)
            .order_by(BusinessBrief.version.desc())
        )
        if b is None:
            raise NotFoundError("No brief yet")
        if patch.offer is not None:
            b.offer = patch.offer
        if patch.audience is not None:
            b.audience = patch.audience
        if patch.usp is not None:
            b.usp = patch.usp
        if patch.objections is not None:
            b.objections = patch.objections
        if patch.tone is not None:
            b.tone = patch.tone
        return {"id": str(b.id), "offer": b.offer, "audience": b.audience, "usp": b.usp,
                "objections": b.objections, "tone": b.tone, "version": b.version}


class AnglePatch(BaseModel):
    status: str


@router.patch("/angles/{angle_id}")
def update_angle(
    angle_id: str, patch: AnglePatch, principal: Principal = Depends(current_principal)
) -> dict:
    if patch.status not in {"ACTIVE", "PAUSED", "REJECTED"}:
        raise ValidationError(f"Invalid angle status: {patch.status}")
    with tenant_session(principal.tenant_id) as s:
        a = s.get(Angle, angle_id)
        if a is None:
            raise NotFoundError("Angle not found")
        require_account_access(principal, str(a.account_id))
        a.status = patch.status
        return {"id": str(a.id), "status": a.status}


@router.post("/accounts/{account_id}/campaigns/launch")
def launch(account_id: str, principal: Principal = Depends(current_principal)) -> dict:
    require_account_access(principal, account_id)
    # Enforce the monthly spend cap before putting anything live (money safety).
    with tenant_session(principal.tenant_id) as s:
        profile = s.scalar(
            select(BusinessProfile).where(BusinessProfile.account_id == account_id)
        )
        cap = profile.monthly_cap_paise if profile else None
        capped = check_monthly_cap(
            month_to_date_paise=month_to_date_spend(s, account_id), monthly_cap_paise=cap
        )
        if not capped.ok:
            raise ValidationError(
                "Monthly spend cap reached — raise it in Settings to launch more ads.",
                user_message_key="error.monthly_cap",
            )
    if (q := _maybe_enqueue("launch", principal.tenant_id, account_id)):
        return q
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
    if (q := _maybe_enqueue("optimize", principal.tenant_id, account_id)):
        return q
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
    if (q := _maybe_enqueue("report", principal.tenant_id, account_id)):
        return q
    with tenant_session(principal.tenant_id) as s:
        msg = pipeline.run_report(s, tenant_id=principal.tenant_id, account_id=account_id)
    return {"message": msg}


@router.get("/accounts/{account_id}/approvals")
def list_approvals(account_id: str, principal: Principal = Depends(current_principal)) -> list[dict]:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        rows = s.scalars(
            select(Approval).where(Approval.account_id == account_id, Approval.status == "PENDING")
        ).all()
        return [{"id": str(a.id), "kind": a.kind, "payload": a.payload, "status": a.status}
                for a in rows]


@router.post("/approvals/{approval_id}/decide")
def decide_approval(
    approval_id: str, approve: bool = True, principal: Principal = Depends(current_principal)
) -> dict:
    with tenant_session(principal.tenant_id) as s:
        ap = s.get(Approval, approval_id)
        if ap is None:
            return {"ok": False}
        require_account_access(principal, str(ap.account_id))
        ap.status = "APPROVED" if approve else "REJECTED"
        # Approving a creative batch promotes its creatives to launch-ready.
        if approve and ap.kind == "CREATIVE_BATCH":
            for cid in ap.payload.get("creative_ids", []):
                c = s.get(Creative, cid)
                if c is not None and c.compliance_status == "PASSED":
                    c.approval_status = "APPROVED_FOR_LAUNCH"
        return {"ok": True, "status": ap.status}
