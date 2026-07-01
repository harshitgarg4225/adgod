"""Orchestrator — deterministic control loop (PRD §4.3, §11.1).

Plain code, not an LLM. It loads account state, routes a trigger to the relevant
sub-agent, passes the result through the Guardrail Engine, persists state + an
audit trail, and enqueues notifications/effects. The same Orchestrator runs in the
BFF (synchronous owner triggers) and in workers (queued/cron), so behavior is
identical regardless of what fired the trigger.

v1 implements the CLOSER (inbound WhatsApp) path end to end. Scout/Maker/Buyer/
Optimizer/Reporter routing is added in later phases behind the same loop.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from leadpilot.common.i18n import t
from leadpilot.common.logging import get_logger, redact_text
from leadpilot.core.enums import (
    ConversationState,
    LeadScore,
    LeadStatus,
    MessageDirection,
    MessageStatus,
    MessageType,
    NotificationKind,
)
from leadpilot.core.models import (
    Account,
    Booking,
    BusinessProfile,
    Conversation,
    Lead,
    LeadQualification,
    Message,
    Notification,
)
from leadpilot.core.outbox import enqueue_effect
from leadpilot.integrations.whatsapp.base import InboundMessage
from leadpilot.saathi.agents.closer import CloserAgent
from leadpilot.saathi.guardrails.engine import GuardrailEngine
from leadpilot.saathi.outbound import enqueue_send
from leadpilot.saathi.textutil import is_junk

log = get_logger("orchestrator")

_TERMINAL = {
    LeadStatus.WON, LeadStatus.LOST, LeadStatus.NO_RESPONSE,
    LeadStatus.SPAM, LeadStatus.DISQUALIFIED_COLD,
}
_FREE_WINDOW = timedelta(hours=72)

_SCORE_TO_STATUS = {
    LeadScore.HOT: LeadStatus.QUALIFIED_HOT,
    LeadScore.WARM: LeadStatus.QUALIFIED_WARM,
    LeadScore.COLD: LeadStatus.DISQUALIFIED_COLD,
    LeadScore.SPAM: LeadStatus.SPAM,
}


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class InboundResult:
    lead_id: UUID
    conversation_id: UUID
    sent: bool
    blocked: bool
    score: str | None
    next_state: str
    hot: bool


class Orchestrator:
    def __init__(self) -> None:
        self.closer = CloserAgent()

    # ───────────────────────── Inbound (CLOSER trigger) ─────────────────────────

    def handle_inbound(
        self, session: Session, *, tenant_id: UUID, account_id: UUID, inbound: InboundMessage
    ) -> InboundResult:
        account = session.get(Account, account_id)
        if account is None:
            raise ValueError(f"account {account_id} not found in tenant context")

        # Idempotency: if this inbound message was already processed (task retry /
        # redelivery that slipped past intake dedupe), return without re-applying.
        already = session.scalar(
            select(Message).where(
                Message.wa_message_id == inbound.wa_message_id,
                Message.direction == MessageDirection.IN.value,
            )
        )
        if already is not None:
            conv = session.get(Conversation, already.conversation_id)
            return InboundResult(conv.lead_id, conv.id, sent=False, blocked=False,
                                 score=None, next_state=conv.state, hot=False)

        profile = session.scalar(
            select(BusinessProfile).where(BusinessProfile.account_id == account_id)
        )
        city = (profile.service_area_city if profile else None) or "your city"
        language = account.default_language or "hi"

        lead = self._find_or_create_lead(session, tenant_id, account_id, inbound)
        conversation = self._find_or_create_conversation(session, tenant_id, lead)

        # Persist inbound message. Each inbound reopens the 24h free-form service window
        # (Meta resets it on every customer message), so refresh the expiry — proactive
        # outbound (re-engagement/reports) checks this to decide free-form vs. template.
        conversation.last_inbound_at = _now()
        conversation.free_window_expires_at = _now() + _FREE_WINDOW
        session.add(
            Message(
                tenant_id=tenant_id,
                conversation_id=conversation.id,
                direction=MessageDirection.IN.value,
                wa_message_id=inbound.wa_message_id,
                type=MessageType.TEXT.value,
                body=inbound.text,
                redacted_body=redact_text(inbound.text),
                status=MessageStatus.DELIVERED.value,
            )
        )
        session.flush()

        junk_turns = self._prior_junk_turns(session, conversation.id)
        state = conversation.state

        try:
            output = self.closer.run(
                session,
                tenant_id=tenant_id,
                account_id=account_id,
                state=state,
                captured=self._lead_captured(lead),
                user_text=inbound.text,
                business_name=account.business_name,
                category=account.category,
                city=city,
                language=language,
                junk_turns=junk_turns,
                input_ref=inbound.wa_message_id,
            )
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, never drop a paid lead
            # LLM/provider down or budget exceeded: send a safe canned acknowledgement and
            # hand the chat to the owner, rather than leaving the lead with no reply.
            log.warning("closer_degraded", lead_id=str(lead.id), error=str(exc)[:200])
            return self._degrade_to_handoff(
                session, tenant_id, account_id, lead, conversation, inbound, language
            )

        guard = GuardrailEngine(session, tenant_id=tenant_id, account_id=account_id)
        scope = guard.closer_scope(output)
        if not scope.ok:
            conversation.state = ConversationState.HANDOFF.value
            lead.status = LeadStatus.HANDED_OFF.value
            self._notify(
                session, tenant_id, account_id, NotificationKind.ANOMALY,
                title="Conversation needs your attention",
                body="Saathi paused an off-script reply. Please take over this chat.",
                ref_id=lead.id,
            )
            log.warning("closer_blocked", lead_id=str(lead.id), reason=scope.detail)
            return InboundResult(lead.id, conversation.id, sent=False, blocked=True,
                                 score=None, next_state=conversation.state, hot=False)

        # Persist outbound message (QUEUED) and enqueue the send through the outbox.
        out_msg = Message(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            direction=MessageDirection.OUT.value,
            type=(MessageType.INTERACTIVE.value if output.reply.type == "interactive"
                  else MessageType.TEXT.value),
            body=output.reply.body,
            redacted_body=redact_text(output.reply.body),
            status=MessageStatus.QUEUED.value,
        )
        session.add(out_msg)
        session.flush()

        enqueue_effect(
            session,
            tenant_id=tenant_id,
            account_id=account_id,
            step_id=f"{inbound.wa_message_id}:reply",
            effect_type="whatsapp_send",
            payload={
                "message_id": str(out_msg.id),
                "phone_number_id": inbound.phone_number_id,
                "to_phone": inbound.from_phone,
                "kind": output.reply.type,
                "body": output.reply.body,
                "buttons": [b.model_dump() for b in (output.reply.buttons or [])],
            },
        )

        conversation.state = output.next_state.value
        conversation.last_outbound_at = _now()
        self._apply_captured(lead, output)

        # Autonomous booking: when the Closer moves the chat into BOOK, record a PROPOSED
        # booking so the appointment surfaces in the owner's calendar surface. Idempotent —
        # one open booking per lead.
        if output.next_state == ConversationState.BOOK:
            self._ensure_booking(session, tenant_id, account_id, lead)

        if lead.status == LeadStatus.NEW.value:
            lead.status = LeadStatus.ENGAGED.value

        hot = False
        if output.score is not None:
            self._record_qualification(session, tenant_id, lead, output)
            hot = output.score == LeadScore.HOT
            if hot:
                self._notify(
                    session, tenant_id, account_id, NotificationKind.HOT_LEAD,
                    title=t("notify.hot_lead.title", language),
                    body=t("notify.hot_lead.body", language,
                           name=lead.name or "A customer",
                           intent=lead.intent_summary or "your service"),
                    ref_id=lead.id,
                )

        return InboundResult(lead.id, conversation.id, sent=True, blocked=False,
                             score=output.score.value if output.score else None,
                             next_state=conversation.state, hot=hot)

    # ───────────────────────── helpers ─────────────────────────

    def _find_or_create_lead(
        self, session: Session, tenant_id: UUID, account_id: UUID, inbound: InboundMessage
    ) -> Lead:
        existing = session.scalars(
            select(Lead)
            .where(Lead.account_id == account_id, Lead.wa_phone == inbound.from_phone)
            .order_by(Lead.created_at.desc())
        ).first()
        if existing and existing.status not in {s.value for s in _TERMINAL}:
            return existing
        lead = Lead(
            tenant_id=tenant_id,
            account_id=account_id,
            source_channel="META_CTWA",
            wa_phone=inbound.from_phone,
            status=LeadStatus.NEW.value,
            first_msg_at=_now(),
        )
        session.add(lead)
        session.flush()
        return lead

    def _find_or_create_conversation(
        self, session: Session, tenant_id: UUID, lead: Lead
    ) -> Conversation:
        conv = session.scalar(select(Conversation).where(Conversation.lead_id == lead.id))
        if conv:
            return conv
        conv = Conversation(
            tenant_id=tenant_id,
            lead_id=lead.id,
            channel="WHATSAPP",
            state=ConversationState.GREET.value,
            free_window_expires_at=_now() + _FREE_WINDOW,
        )
        session.add(conv)
        session.flush()
        return conv

    def _prior_junk_turns(self, session: Session, conversation_id: UUID) -> int:
        bodies = session.scalars(
            select(Message.body).where(
                Message.conversation_id == conversation_id,
                Message.direction == MessageDirection.IN.value,
            )
        ).all()
        # Exclude the just-inserted current message (last one).
        return sum(1 for b in bodies[:-1] if is_junk(b or ""))

    @staticmethod
    def _lead_captured(lead: Lead) -> dict:
        return {
            "name": lead.name,
            "intent": lead.intent_summary,
            "budget": lead.budget_signal,
            "timeline": lead.timeline_signal,
            "location": lead.location_signal,
        }

    @staticmethod
    def _apply_captured(lead: Lead, output) -> None:
        c = output.captured
        lead.name = c.name or lead.name
        lead.intent_summary = c.intent or lead.intent_summary
        lead.budget_signal = c.budget or lead.budget_signal
        lead.timeline_signal = c.timeline or lead.timeline_signal
        lead.location_signal = c.location or lead.location_signal

    def _record_qualification(self, session: Session, tenant_id: UUID, lead: Lead, output) -> None:
        score = output.score
        session.add(
            LeadQualification(
                tenant_id=tenant_id,
                lead_id=lead.id,
                score=score.value,
                reasons=output.score_reasons,
                captured=output.captured.model_dump(),
                model_version=self.closer.llm.model_for("closer"),
            )
        )
        lead.score = score.value
        lead.status = _SCORE_TO_STATUS[score].value
        if score in (LeadScore.HOT, LeadScore.WARM):
            lead.qualified_at = _now()

    @staticmethod
    def _notify(
        session: Session, tenant_id: UUID, account_id: UUID, kind: NotificationKind,
        *, title: str, body: str, ref_id: UUID | None = None,
    ) -> None:
        session.add(
            Notification(
                tenant_id=tenant_id, account_id=account_id, kind=kind.value,
                title=title, body=body, ref_id=ref_id,
            )
        )

    def _degrade_to_handoff(
        self, session: Session, tenant_id: UUID, account_id: UUID, lead: Lead,
        conversation: Conversation, inbound: InboundMessage, language: str,
    ) -> InboundResult:
        """Fallback when the Closer LLM is unavailable: acknowledge the lead with a safe
        canned message (inside the still-open service window) and hand off to the owner."""
        body = (
            "धन्यवाद! 🙏 हमारी टीम आपसे जल्द ही संपर्क करेगी।"
            if language == "hi"
            else "Thank you! 🙏 Our team will reach out to you shortly."
        )
        enqueue_send(
            session,
            tenant_id=tenant_id,
            account_id=account_id,
            conversation_id=conversation.id,
            phone_number_id=inbound.phone_number_id,
            to_phone=inbound.from_phone,
            step_id=f"{inbound.wa_message_id}:degraded",
            kind="text",
            body=body,
        )
        conversation.state = ConversationState.HANDOFF.value
        conversation.last_outbound_at = _now()
        lead.status = LeadStatus.HANDED_OFF.value
        self._notify(
            session, tenant_id, account_id, NotificationKind.ANOMALY,
            title="A lead needs your attention",
            body="Saathi couldn't auto-reply just now. Please take over this chat.",
            ref_id=lead.id,
        )
        return InboundResult(
            lead.id, conversation.id, sent=True, blocked=False,
            score=None, next_state=conversation.state, hot=False,
        )

    @staticmethod
    def _ensure_booking(session: Session, tenant_id: UUID, account_id: UUID, lead: Lead) -> None:
        existing = session.scalar(
            select(Booking).where(Booking.lead_id == lead.id, Booking.status != "CANCELLED")
        )
        if existing is None:
            session.add(Booking(tenant_id=tenant_id, account_id=account_id, lead_id=lead.id))


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
