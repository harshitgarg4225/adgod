"""Owner surfaces: Lead Inbox (CRM-lite), lead detail + transcript, owner actions,
home dashboard, notifications (PRD §6.7, §6.8, §12.1)."""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select

from leadpilot.bff.deps import Principal, current_principal, require_account_access
from leadpilot.bff.schemas import (
    HomeOut,
    LeadDetailOut,
    LeadListItem,
    LeadPatch,
    MessageOut,
    NotificationOut,
)
from leadpilot.common.errors import NotFoundError, ValidationError
from leadpilot.core.db import tenant_session
from leadpilot.core.enums import AccountPhase, LeadScore, LeadStatus, OwnerAction
from leadpilot.core.models import (
    Account,
    AdInsight,
    BusinessProfile,
    Conversation,
    Lead,
    Message,
    Notification,
)
from leadpilot.core.money import format_paise

router = APIRouter(tags=["leads"])


def _csv_safe(value: str) -> str:
    """Neutralise CSV formula injection: a cell starting with = + - @ (or a leading tab/CR)
    is treated as a formula by Excel/Sheets. Prefix with an apostrophe so attacker-supplied
    lead text can't execute when the owner opens the export."""
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


_SCORE_RANK = case(
    {LeadScore.HOT.value: 0, LeadScore.WARM.value: 1, LeadScore.COLD.value: 2,
     LeadScore.SPAM.value: 3},
    value=Lead.score,
    else_=4,
)


@router.get("/accounts/{account_id}/leads", response_model=list[LeadListItem])
def list_leads(
    account_id: str,
    status: str | None = Query(default=None),
    score: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    principal: Principal = Depends(current_principal),
) -> list[LeadListItem]:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as session:
        stmt = select(Lead).where(Lead.account_id == account_id)
        if status:
            stmt = stmt.where(Lead.status == status)
        if score:
            stmt = stmt.where(Lead.score == score)
        if q:
            like = f"%{q}%"
            stmt = stmt.where((Lead.name.ilike(like)) | (Lead.wa_phone.ilike(like)))
        stmt = stmt.order_by(_SCORE_RANK, Lead.created_at.desc()).limit(limit)
        rows = session.scalars(stmt).all()
        return [
            LeadListItem(
                id=r.id, name=r.name, intent_summary=r.intent_summary, score=r.score,
                status=r.status, source_channel=r.source_channel, owner_action=r.owner_action,
                created_at=r.created_at, first_msg_at=r.first_msg_at,
            )
            for r in rows
        ]


@router.get("/leads/{lead_id}", response_model=LeadDetailOut)
def get_lead(lead_id: str, principal: Principal = Depends(current_principal)) -> LeadDetailOut:
    with tenant_session(principal.tenant_id) as session:
        lead = session.get(Lead, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        require_account_access(principal, str(lead.account_id))
        conv = session.scalar(select(Conversation).where(Conversation.lead_id == lead.id))
        transcript: list[MessageOut] = []
        if conv is not None:
            msgs = session.scalars(
                select(Message).where(Message.conversation_id == conv.id)
                .order_by(Message.created_at)
            ).all()
            transcript = [
                MessageOut(direction=m.direction, type=m.type, body=m.body,
                           status=m.status, created_at=m.created_at)
                for m in msgs
            ]
        return LeadDetailOut(
            id=lead.id, name=lead.name, wa_phone=lead.wa_phone, score=lead.score,
            status=lead.status, intent_summary=lead.intent_summary,
            budget_signal=lead.budget_signal, timeline_signal=lead.timeline_signal,
            location_signal=lead.location_signal, owner_action=lead.owner_action,
            source_channel=lead.source_channel, created_at=lead.created_at,
            qualified_at=lead.qualified_at, transcript=transcript,
        )


@router.patch("/leads/{lead_id}", response_model=LeadDetailOut)
def patch_lead(
    lead_id: str, patch: LeadPatch, principal: Principal = Depends(current_principal)
) -> LeadDetailOut:
    valid_actions = {a.value for a in OwnerAction}
    valid_status = {s.value for s in LeadStatus}
    if patch.owner_action and patch.owner_action not in valid_actions:
        raise ValidationError(f"Invalid owner_action: {patch.owner_action}")
    if patch.status and patch.status not in valid_status:
        raise ValidationError(f"Invalid status: {patch.status}")
    with tenant_session(principal.tenant_id) as session:
        lead = session.get(Lead, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        require_account_access(principal, str(lead.account_id))
        if patch.owner_action:
            lead.owner_action = patch.owner_action
        if patch.status:
            lead.status = patch.status
    return get_lead(lead_id, principal)


@router.get("/accounts/{account_id}/home", response_model=HomeOut)
def home(account_id: str, principal: Principal = Depends(current_principal)) -> HomeOut:
    require_account_access(principal, account_id)
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    qualified = {LeadStatus.QUALIFIED_HOT.value, LeadStatus.QUALIFIED_WARM.value}
    with tenant_session(principal.tenant_id) as session:
        enquiries = session.scalar(
            select(func.count(Lead.id)).where(
                Lead.account_id == account_id, Lead.created_at >= start
            )
        ) or 0
        qualified_today = session.scalar(
            select(func.count(Lead.id)).where(
                Lead.account_id == account_id, Lead.created_at >= start,
                Lead.status.in_(qualified),
            )
        ) or 0
        # Real spend from ad_insights (account level) for today.
        spend = int(session.scalar(
            select(func.coalesce(func.sum(AdInsight.spend_paise), 0)).where(
                AdInsight.account_id == account_id,
                AdInsight.level == "ACCOUNT",
                AdInsight.date >= start,
            )
        ) or 0)
        # Last 7 days spend, oldest→newest, for the dashboard sparkline.
        week_start = start - timedelta(days=6)
        per_day = dict(session.execute(
            select(func.date(AdInsight.date), func.coalesce(func.sum(AdInsight.spend_paise), 0))
            .where(AdInsight.account_id == account_id, AdInsight.level == "ACCOUNT",
                   AdInsight.date >= week_start)
            .group_by(func.date(AdInsight.date))
        ).all())
        spend_trend = [
            int(per_day.get((week_start + timedelta(days=i)).date(), 0)) for i in range(7)
        ]
        account = session.get(Account, account_id)
        profile = session.scalar(
            select(BusinessProfile).where(BusinessProfile.account_id == account_id)
        )
        unread = int(session.scalar(
            select(func.count(Notification.id)).where(
                Notification.account_id == account_id, Notification.read_at.is_(None)
            )
        ) or 0)

    phase = account.phase if account else AccountPhase.SIGNED_UP.value
    paused = phase == AccountPhase.PAUSED.value
    daily_budget = profile.daily_budget_paise if profile else 0
    cpql = (spend // qualified_today) if qualified_today else None
    return HomeOut(
        today_spend_paise=spend,
        today_spend_display=format_paise(spend),
        enquiries_today=int(enquiries),
        qualified_today=int(qualified_today),
        cpql_paise=cpql,
        cpql_display=format_paise(cpql) if cpql is not None else None,
        campaign_status=_phase_status(phase),
        phase=phase,
        autopilot_level=account.autopilot_level if account else "ASSISTED",
        paused=paused,
        daily_budget_paise=daily_budget,
        daily_budget_display=format_paise(daily_budget),
        saathi_status=_saathi_status(phase, paused, int(qualified_today)),
        unread_notifications=unread,
        spend_trend=spend_trend,
    )


def _phase_status(phase: str) -> list[str]:
    return {
        AccountPhase.SIGNED_UP.value: ["Finish setup"],
        AccountPhase.ONBOARDING.value: ["Finishing setup"],
        AccountPhase.PENDING_APPROVAL.value: ["In review"],
        AccountPhase.LIVE.value: ["Live"],
        AccountPhase.OPTIMIZING.value: ["Live", "Optimizing"],
        AccountPhase.PAUSED.value: ["Paused"],
    }.get(phase, [phase.replace("_", " ").title()])


def _saathi_status(phase: str, paused: bool, qualified_today: int) -> str:
    if paused:
        return "Your ads are paused. Resume whenever you're ready."
    if phase in (AccountPhase.SIGNED_UP.value, AccountPhase.ONBOARDING.value):
        return "Let's finish setting up so I can start finding leads for you."
    if phase == AccountPhase.PENDING_APPROVAL.value:
        return "Your ads are in review — I'll start them the moment they're approved."
    if qualified_today:
        return f"I've qualified {qualified_today} lead(s) for you today. Keep going! 🎉"
    return "I'm watching your ads 24×7 and qualifying every lead that comes in."


@router.get("/accounts/{account_id}/leads/export.csv")
def export_leads_csv(
    account_id: str, principal: Principal = Depends(current_principal)
) -> StreamingResponse:
    """Export leads as CSV (PRD §6.7.2, Pro). PII stays within the owner's own tenant (RLS)."""
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as session:
        rows = session.scalars(
            select(Lead).where(Lead.account_id == account_id)
            .order_by(Lead.created_at.desc())
        ).all()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["name", "phone", "score", "status", "intent", "location",
                    "owner_action", "created_at"])
        for r in rows:
            w.writerow([_csv_safe(r.name or ""), _csv_safe(r.wa_phone), r.score or "",
                        r.status, _csv_safe(r.intent_summary or ""),
                        _csv_safe(r.location_signal or ""), r.owner_action,
                        r.created_at.isoformat()])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@router.get("/accounts/{account_id}/notifications", response_model=list[NotificationOut])
def notifications(
    account_id: str, limit: int = Query(default=30, le=100),
    principal: Principal = Depends(current_principal),
) -> list[NotificationOut]:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as session:
        rows = session.scalars(
            select(Notification).where(Notification.account_id == account_id)
            .order_by(Notification.created_at.desc()).limit(limit)
        ).all()
        return [
            NotificationOut(
                id=n.id, kind=n.kind, title=n.title, body=n.body, ref_id=n.ref_id,
                read_at=n.read_at, created_at=n.created_at,
            )
            for n in rows
        ]


@router.post("/accounts/{account_id}/notifications/read")
def mark_notifications_read(
    account_id: str, principal: Principal = Depends(current_principal)
) -> dict:
    """Mark all of the account's notifications read (clears the unread badge)."""
    require_account_access(principal, account_id)
    now = datetime.now(UTC)
    with tenant_session(principal.tenant_id) as session:
        rows = session.scalars(
            select(Notification).where(
                Notification.account_id == account_id, Notification.read_at.is_(None)
            )
        ).all()
        for n in rows:
            n.read_at = now
    return {"marked": len(rows)}
