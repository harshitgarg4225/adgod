"""Owner surfaces: Lead Inbox (CRM-lite), lead detail + transcript, owner actions,
home dashboard, notifications (PRD §6.7, §6.8, §12.1)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
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
from leadpilot.core.enums import LeadScore, LeadStatus, OwnerAction
from leadpilot.core.models import Conversation, Lead, Message, Notification
from leadpilot.core.money import format_paise

router = APIRouter(tags=["leads"])

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
    # Spend/CPQL come from ad_insights in Phase 2/3; 0 in the walking skeleton.
    spend = 0
    return HomeOut(
        today_spend_paise=spend,
        today_spend_display=format_paise(spend),
        enquiries_today=int(enquiries),
        qualified_today=int(qualified_today),
        cpql_paise=None,
        cpql_display=None,
        campaign_status=["In review"],
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
