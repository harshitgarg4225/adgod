"""Owner surfaces: Lead Inbox (CRM-lite), lead detail + transcript, owner actions,
home dashboard, notifications (PRD §6.7, §6.8, §12.1)."""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
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
from leadpilot.common.clock import ist_day_start, ist_week_start
from leadpilot.common.errors import NotFoundError, ValidationError
from leadpilot.common.phone import normalize_phone
from leadpilot.common.ratelimit import enforce
from leadpilot.core.db import tenant_session
from leadpilot.core.enums import (
    AccountPhase,
    ConversationState,
    LeadScore,
    LeadStatus,
    OwnerAction,
)
from leadpilot.core.models import (
    Account,
    AdInsight,
    BusinessProfile,
    Conversation,
    Lead,
    Message,
    Notification,
    WhatsAppConnection,
)
from leadpilot.core.money import format_paise
from leadpilot.saathi.outbound import enqueue_send

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


class LeadCreateIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    wa_phone: str = Field(min_length=5, max_length=20)
    intent_summary: str | None = Field(default=None, max_length=2000)
    score: str | None = None
    status: str | None = None


@router.post("/accounts/{account_id}/leads", status_code=201)
def create_lead(
    account_id: str, body: LeadCreateIn, principal: Principal = Depends(current_principal)
) -> dict:
    """Manual lead entry — essential on the own-number (APP_DESTINATION) path, where
    enquiries land in the owner's WhatsApp and never touch our servers. Logging them here
    is what makes the inbox, reports, CPQL and ROAS real. Idempotent per phone+account
    (re-adding an existing phone returns the existing lead)."""
    require_account_access(principal, account_id)
    if body.score and body.score not in {s.value for s in LeadScore}:
        raise ValidationError(f"Invalid score: {body.score}")
    if body.status and body.status not in {s.value for s in LeadStatus}:
        raise ValidationError(f"Invalid status: {body.status}")
    phone = normalize_phone(body.wa_phone)
    with tenant_session(principal.tenant_id) as session:
        existing = session.scalar(select(Lead).where(
            Lead.account_id == account_id, Lead.wa_phone == phone))
        if existing is not None:
            return {"id": str(existing.id), "created": False}
        lead = Lead(
            tenant_id=principal.tenant_id, account_id=account_id, source_channel="MANUAL",
            wa_phone=phone, name=body.name, intent_summary=body.intent_summary,
            score=body.score, status=body.status or LeadStatus.NEW.value,
            first_msg_at=datetime.now(UTC),
        )
        session.add(lead)
        session.flush()
        return {"id": str(lead.id), "created": True}


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
        # In-app WhatsApp replies only work with a Cloud API number + an open
        # conversation window — hide the dead composer on the own-number path.
        wa = session.scalar(select(WhatsAppConnection).where(
            WhatsAppConnection.account_id == lead.account_id))
        can_message = bool(wa and wa.mode == "CLOUD_API" and wa.phone_number_id
                           and conv is not None)
        return LeadDetailOut(
            id=lead.id, name=lead.name, wa_phone=lead.wa_phone, score=lead.score,
            status=lead.status, intent_summary=lead.intent_summary,
            budget_signal=lead.budget_signal, timeline_signal=lead.timeline_signal,
            location_signal=lead.location_signal, owner_action=lead.owner_action,
            source_channel=lead.source_channel, created_at=lead.created_at,
            qualified_at=lead.qualified_at, transcript=transcript,
            can_message=can_message,
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


class OwnerMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/leads/{lead_id}/message")
def send_owner_message(
    lead_id: str, body: OwnerMessageIn, principal: Principal = Depends(current_principal)
) -> dict:
    """Owner sends a WhatsApp reply from the app (in-app takeover). Free-form text is only
    valid inside the 24h service window; outside it we ask the owner to use a call/template
    instead of silently failing at Meta."""
    now = datetime.now(UTC)
    # Cost control: WhatsApp sends cost money — bound a runaway/compromised session.
    enforce("owner_msg", str(principal.account_id or principal.user_id),
            limit=60, window_s=3600)
    with tenant_session(principal.tenant_id) as session:
        lead = session.get(Lead, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        require_account_access(principal, str(lead.account_id))
        conv = session.scalar(select(Conversation).where(Conversation.lead_id == lead.id))
        if conv is None:
            raise ValidationError("No conversation for this lead yet")
        if conv.free_window_expires_at and conv.free_window_expires_at < now:
            raise ValidationError(
                "The free 24-hour window has closed. Please call the lead instead.",
                user_message_key="error.window_closed",
            )
        wa = session.scalar(
            select(WhatsAppConnection).where(WhatsAppConnection.account_id == lead.account_id)
        )
        if wa is None or not wa.phone_number_id:
            raise ValidationError("WhatsApp is not connected for this account")
        msg = enqueue_send(
            session,
            tenant_id=lead.tenant_id,
            account_id=lead.account_id,
            conversation_id=conv.id,
            phone_number_id=wa.phone_number_id,
            to_phone=lead.wa_phone,
            step_id=f"owner:{uuid4()}",
            kind="text",
            body=body.text,
        )
        conv.last_outbound_at = now
        # Owner takeover — Saathi steps back on this chat.
        conv.state = ConversationState.HANDOFF.value
        lead.owner_action = OwnerAction.CALLED.value
        return {"message_id": str(msg.id), "status": "queued"}


@router.get("/accounts/{account_id}/home", response_model=HomeOut)
def home(account_id: str, principal: Principal = Depends(current_principal)) -> HomeOut:
    require_account_access(principal, account_id)
    start = ist_day_start()  # business day = IST, matching the insight snapshots
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
        week_start = ist_week_start()
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
        wa_mode = session.scalar(
            select(WhatsAppConnection.mode).where(
                WhatsAppConnection.account_id == account_id)
        )

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
        saathi_status=_saathi_status(phase, paused, int(qualified_today), wa_mode),
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


def _saathi_status(phase: str, paused: bool, qualified_today: int,
                   wa_mode: str | None = None) -> str:
    if paused:
        return "Your ads are paused. Resume whenever you're ready."
    if phase in (AccountPhase.SIGNED_UP.value, AccountPhase.ONBOARDING.value):
        return "Let's finish setting up so I can start finding leads for you."
    if phase == AccountPhase.PENDING_APPROVAL.value:
        return "Your ads are in review — I'll start them the moment they're approved."
    if qualified_today:
        return f"I've qualified {qualified_today} lead(s) for you today. Keep going! 🎉"
    if wa_mode == "APP_DESTINATION":
        # Own-number mode: chats land in the owner's WhatsApp, not here — never claim
        # we're qualifying what we cannot see.
        return ("Your ads send customers straight to your WhatsApp. "
                "Log enquiries here so I can track your results.")
    return "I'm watching your ads 24×7 and qualifying every lead that comes in."


@router.get("/accounts/{account_id}/leads/export.csv")
def export_leads_csv(
    account_id: str, principal: Principal = Depends(current_principal)
) -> StreamingResponse:
    """Export leads as CSV (PRD §6.7.2, Pro). PII stays within the owner's own tenant (RLS).

    Streamed with a server-side cursor (yield_per) so a large export never materialises the
    whole table in memory."""
    require_account_access(principal, account_id)
    tenant_id = principal.tenant_id

    def _row(values: list) -> str:
        buf = io.StringIO()
        csv.writer(buf).writerow(values)
        return buf.getvalue()

    def _stream():
        yield _row(["name", "phone", "score", "status", "intent", "location",
                    "owner_action", "created_at"])
        # The session stays open for the life of the generator (StreamingResponse pulls lazily).
        with tenant_session(tenant_id) as session:
            result = session.execute(
                select(Lead).where(Lead.account_id == account_id)
                .order_by(Lead.created_at.desc())
                .execution_options(yield_per=500)
            )
            for r in result.scalars():
                yield _row([_csv_safe(r.name or ""), _csv_safe(r.wa_phone), r.score or "",
                            r.status, _csv_safe(r.intent_summary or ""),
                            _csv_safe(r.location_signal or ""), r.owner_action,
                            r.created_at.isoformat()])

    return StreamingResponse(
        _stream(), media_type="text/csv",
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
