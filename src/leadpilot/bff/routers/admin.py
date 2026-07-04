"""Admin / ops back-office (PRD §6.11) — role OPS/ADMIN only.

Cross-tenant reads/writes run via the platform role (BYPASSRLS); every sensitive action
(impersonation, manual pause) is written to audit_logs. Never reachable by owners/partners.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from leadpilot.bff.deps import Principal, current_principal, require_role
from leadpilot.common.auth import issue_access_token
from leadpilot.common.clock import ist_day_start
from leadpilot.common.errors import NotFoundError
from leadpilot.common.requtil import client_ip
from leadpilot.core.db import platform_session
from leadpilot.core.enums import AccountPhase, CampaignStatus, SubscriptionStatus
from leadpilot.core.models import (
    Account,
    AdInsight,
    AuditLog,
    Campaign,
    FeatureFlag,
    GuardrailEvent,
    Lead,
    MetaConnection,
    Subscription,
    User,
)
from leadpilot.core.money import format_paise

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
    """Fleet overview: the founder's morning check must answer 'is every client healthy'
    in ONE screen — phase, today's spend/leads, and whether the Meta connection is alive."""
    require_role(principal, {"ADMIN", "OPS"})
    day = ist_day_start()
    with platform_session() as s:
        stmt = select(Account).where(Account.deleted_at.is_(None))
        if q:
            stmt = stmt.where(Account.business_name.ilike(f"%{q}%"))
        rows = s.scalars(stmt.limit(limit)).all()
        ids = [a.id for a in rows]
        spend_by = dict(s.execute(
            select(AdInsight.account_id, func.sum(AdInsight.spend_paise)).where(
                AdInsight.account_id.in_(ids), AdInsight.level == "ACCOUNT",
                AdInsight.date >= day).group_by(AdInsight.account_id)).all()) if ids else {}
        leads_by = dict(s.execute(
            select(Lead.account_id, func.count(Lead.id)).where(
                Lead.account_id.in_(ids), Lead.created_at >= day)
            .group_by(Lead.account_id)).all()) if ids else {}
        meta_by = dict(s.execute(
            select(MetaConnection.account_id, MetaConnection.status).where(
                MetaConnection.account_id.in_(ids))).all()) if ids else {}
        return [{"id": str(a.id), "tenant_id": str(a.tenant_id), "business_name": a.business_name,
                 "category": a.category, "phase": a.phase, "autopilot": a.autopilot_level,
                 "trust_score": a.trust_score,
                 "today_spend_paise": int(spend_by.get(a.id, 0) or 0),
                 "today_spend_display": format_paise(int(spend_by.get(a.id, 0) or 0)),
                 "leads_today": int(leads_by.get(a.id, 0) or 0),
                 "meta_status": meta_by.get(a.id, "NONE")} for a in rows]


@router.get("/digest")
def operator_digest(principal: Principal = Depends(current_principal)) -> dict:
    """Per-client daily summary, computed live — the founder copies this into WhatsApp
    for each client (the own-number path has no automated owner delivery yet)."""
    require_role(principal, {"ADMIN", "OPS"})
    day = ist_day_start()
    qualified = {"QUALIFIED_HOT", "QUALIFIED_WARM"}
    lines: list[dict] = []
    with platform_session() as s:
        accounts = s.scalars(select(Account).where(
            Account.deleted_at.is_(None),
            Account.phase.in_(["LIVE", "OPTIMIZING", "FATIGUE_REFRESH", "PAUSED"]))).all()
        for a in accounts:
            spend = int(s.scalar(select(func.coalesce(func.sum(AdInsight.spend_paise), 0)).where(
                AdInsight.account_id == a.id, AdInsight.level == "ACCOUNT",
                AdInsight.date >= day)) or 0)
            enquiries = int(s.scalar(select(func.count(Lead.id)).where(
                Lead.account_id == a.id, Lead.created_at >= day)) or 0)
            qual = int(s.scalar(select(func.count(Lead.id)).where(
                Lead.account_id == a.id, Lead.created_at >= day,
                Lead.status.in_(qualified))) or 0)
            text_block = (f"*{a.business_name}* — aaj ka update\n"
                          f"Kharcha: {format_paise(spend)} | Enquiries: {enquiries} | "
                          f"Qualified: {qual}"
                          + (f" | CPQL: {format_paise(spend // qual)}" if qual else ""))
            lines.append({"account_id": str(a.id), "business_name": a.business_name,
                          "phase": a.phase, "spend_paise": spend, "enquiries": enquiries,
                          "qualified": qual, "text": text_block})
    return {"date": day.date().isoformat(), "clients": lines}


@router.post("/accounts/{account_id}/subscription/mark-paid")
def mark_subscription_paid(
    account_id: str, request: Request, principal: Principal = Depends(current_principal)
) -> dict:
    """Manual billing (launch weeks): the founder collected payment by UPI/bank — mark the
    subscription ACTIVE so trial_sweep never pauses a paying client's ads."""
    require_role(principal, {"ADMIN", "OPS"})
    with platform_session() as s:
        sub = s.scalar(select(Subscription).where(Subscription.account_id == account_id))
        if sub is None:
            raise NotFoundError("No subscription for this account")
        before = sub.status
        sub.status = SubscriptionStatus.ACTIVE.value
        sub.current_period_end = datetime.now(UTC) + timedelta(days=30)
        # Paying un-pauses a trial pause (never an owner's deliberate pause).
        acc = s.get(Account, account_id)
        if acc is not None and acc.phase == AccountPhase.PAUSED.value \
                and acc.pause_reason == "trial":
            from leadpilot.saathi.pipeline import set_live_state

            set_live_state(s, tenant_id=acc.tenant_id, account_id=acc.id, pause=False)
        _audit(s, actor=f"user:{principal.user_id}", action="subscription_mark_paid",
               entity="subscription", entity_id=str(sub.id), tenant_id=sub.tenant_id,
               before={"status": before}, after={"status": sub.status},
               ip=client_ip(request))
        return {"ok": True, "status": sub.status}


@router.get("/anomaly-queue")
def anomaly_queue(
    limit: int = Query(default=50, le=200), principal: Principal = Depends(current_principal)
) -> list[dict]:
    require_role(principal, {"ADMIN", "OPS"})
    with platform_session() as s:
        rows = s.execute(
            select(GuardrailEvent, Account.business_name)
            .join(Account, Account.id == GuardrailEvent.account_id, isouter=True)
            .where(GuardrailEvent.type == "ANOMALY")
            .order_by(desc(GuardrailEvent.created_at)).limit(limit)
        ).all()
        return [{"id": str(e.id), "account_id": str(e.account_id),
                 "business_name": name or "?", "severity": e.severity,
                 "detail": e.detail, "action_taken": e.action_taken,
                 "created_at": e.created_at.isoformat()} for e, name in rows]


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
        from leadpilot.saathi.pipeline import set_live_state

        # Pauses Meta delivery too — an admin pause that leaves the campaign spending
        # is not a pause. Falls back to a bare phase flip pre-launch.
        if not set_live_state(s, tenant_id=acc.tenant_id, account_id=acc.id,
                              pause=True, reason="admin"):
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
