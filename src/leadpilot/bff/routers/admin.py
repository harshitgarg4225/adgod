"""Admin / ops back-office (PRD §6.11) — role OPS/ADMIN only.

Cross-tenant reads/writes run via the platform role (BYPASSRLS); every sensitive action
(impersonation, manual pause) is written to audit_logs. Never reachable by owners/partners.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import desc, select

from leadpilot.bff.deps import Principal, current_principal, require_role
from leadpilot.common.auth import issue_access_token
from leadpilot.common.errors import NotFoundError
from leadpilot.common.requtil import client_ip
from leadpilot.core.db import platform_session
from leadpilot.core.enums import AccountPhase, CampaignStatus
from leadpilot.core.models import Account, AuditLog, Campaign, FeatureFlag, GuardrailEvent, User

router = APIRouter(prefix="/admin", tags=["admin"])


def _audit(s, *, actor: str, action: str, entity: str, entity_id: str,
           tenant_id=None, before=None, after=None, ip=None) -> None:
    s.add(AuditLog(tenant_id=tenant_id, actor=actor, action=action, entity=entity,
                   entity_id=entity_id, before=before or {}, after=after or {}, ip=ip))


@router.get("/accounts")
def search_accounts(
    q: str = Query(default=""), limit: int = Query(default=50, le=200),
    principal: Principal = Depends(current_principal),
) -> list[dict]:
    require_role(principal, {"ADMIN", "OPS"})
    with platform_session() as s:
        stmt = select(Account)
        if q:
            stmt = stmt.where(Account.business_name.ilike(f"%{q}%"))
        rows = s.scalars(stmt.limit(limit)).all()
        return [{"id": str(a.id), "tenant_id": str(a.tenant_id), "business_name": a.business_name,
                 "category": a.category, "phase": a.phase, "autopilot": a.autopilot_level,
                 "trust_score": a.trust_score} for a in rows]


@router.get("/anomaly-queue")
def anomaly_queue(
    limit: int = Query(default=50, le=200), principal: Principal = Depends(current_principal)
) -> list[dict]:
    require_role(principal, {"ADMIN", "OPS"})
    with platform_session() as s:
        rows = s.scalars(
            select(GuardrailEvent).where(GuardrailEvent.type == "ANOMALY")
            .order_by(desc(GuardrailEvent.created_at)).limit(limit)
        ).all()
        return [{"id": str(e.id), "account_id": str(e.account_id), "severity": e.severity,
                 "detail": e.detail, "action_taken": e.action_taken,
                 "created_at": e.created_at.isoformat()} for e in rows]


@router.post("/accounts/{account_id}/pause")
def pause_account(
    account_id: str, request: Request, principal: Principal = Depends(current_principal)
) -> dict:
    require_role(principal, {"ADMIN", "OPS"})
    with platform_session() as s:
        acc = s.get(Account, account_id)
        if acc is None:
            raise NotFoundError("Account not found")
        before = acc.phase
        acc.phase = AccountPhase.PAUSED.value
        for camp in s.scalars(select(Campaign).where(Campaign.account_id == acc.id)).all():
            camp.status = CampaignStatus.PAUSED.value
        _audit(s, actor=f"user:{principal.user_id}", action="account_pause", entity="account",
               entity_id=account_id, tenant_id=acc.tenant_id, before={"phase": before},
               after={"phase": acc.phase}, ip=client_ip(request))
        return {"ok": True, "phase": acc.phase}


@router.post("/impersonate/{account_id}")
def impersonate(
    account_id: str, request: Request, principal: Principal = Depends(current_principal)
) -> dict:
    """Issue a scoped owner token for support. Audited (PRD §6.11)."""
    require_role(principal, {"ADMIN", "OPS"})
    with platform_session() as s:
        owner = s.scalar(
            select(User).where(User.account_id == account_id, User.role == "OWNER")
        )
        if owner is None:
            raise NotFoundError("No owner for this account")
        _audit(s, actor=f"user:{principal.user_id}", action="impersonate", entity="account",
               entity_id=account_id, tenant_id=owner.tenant_id,
               ip=client_ip(request))
        token = issue_access_token(user_id=str(owner.id), tenant_id=str(owner.tenant_id),
                                   account_id=str(owner.account_id), role="OWNER",
                                   token_version=owner.token_version)
    return {"access": token, "impersonating": account_id}


class FlagIn(BaseModel):
    key: str
    enabled: bool
    description: str | None = None


@router.get("/feature-flags")
def list_flags(principal: Principal = Depends(current_principal)) -> list[dict]:
    require_role(principal, {"ADMIN", "OPS"})
    with platform_session() as s:
        rows = s.scalars(select(FeatureFlag)).all()
        return [{"key": f.key, "enabled": f.enabled, "description": f.description} for f in rows]


@router.post("/feature-flags")
def set_flag(body: FlagIn, principal: Principal = Depends(current_principal)) -> dict:
    require_role(principal, {"ADMIN"})
    with platform_session() as s:
        flag = s.scalar(select(FeatureFlag).where(FeatureFlag.key == body.key))
        if flag is None:
            flag = FeatureFlag(key=body.key)
            s.add(flag)
        flag.enabled = body.enabled
        flag.description = body.description
        return {"key": body.key, "enabled": body.enabled}
