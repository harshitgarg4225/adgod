"""Scoped-conversation guard (PRD §4.5.3, §6.6.3; v1 AC).

An out-of-scope Closer output is blocked, recorded in guardrail_events, and never
sent via the WhatsApp adapter."""
from __future__ import annotations

import uuid
from dataclasses import asdict

from sqlalchemy import func, select

import leadpilot.integrations.whatsapp.mock as wamock
from leadpilot.core.db import tenant_session
from leadpilot.core.enums import ConversationState
from leadpilot.core.models import GuardrailEvent, Message
from leadpilot.core.routing import record_inbound_event
from leadpilot.integrations.whatsapp.base import InboundMessage
from leadpilot.saathi.agents.closer import CloserAgent
from leadpilot.saathi.contracts import CloserOutput, CloserReply
from leadpilot.saathi.guardrails.scope import check_closer_scope
from leadpilot.scripts.demo_constants import (
    DEMO_ACCOUNT_ID,
    DEMO_PHONE_NUMBER_ID,
    DEMO_TENANT_ID,
)
from leadpilot.worker.tasks.closer import run_inbound


def test_scope_guard_blocks_out_of_scope_outputs():
    long_body = "x" * 700
    assert not check_closer_scope(
        CloserOutput(reply=CloserReply(type="text", body=long_body),
                     next_state=ConversationState.GREET)
    ).ok
    assert not check_closer_scope(
        CloserOutput(reply=CloserReply(type="text", body="```python\nprint(1)```"),
                     next_state=ConversationState.GREET)
    ).ok
    assert not check_closer_scope(
        CloserOutput(reply=CloserReply(type="text", body="As an AI language model, here's a poem"),
                     next_state=ConversationState.GREET)
    ).ok
    # In-scope qualification reply passes.
    assert check_closer_scope(
        CloserOutput(reply=CloserReply(type="text", body="Aapka naam kya hai?"),
                     next_state=ConversationState.CAPTURE_NAME)
    ).ok


def test_orchestrator_blocks_and_does_not_send(seeded, monkeypatch):
    wamock.SENT.clear()

    def bad_run(self, session, **kwargs):
        return CloserOutput(
            reply=CloserReply(type="text", body="```rm -rf /``` here is some code for you"),
            next_state=ConversationState.CAPTURE_NAME,
        )

    monkeypatch.setattr(CloserAgent, "run", bad_run)

    inbound = InboundMessage(
        wa_message_id="wamid." + uuid.uuid4().hex, from_phone="+919800000200",
        phone_number_id=DEMO_PHONE_NUMBER_ID, text="hi",
    )
    event_id = record_inbound_event(
        provider="whatsapp", external_id=inbound.wa_message_id,
        tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
        payload={"message": asdict(inbound)},
    )
    result = run_inbound(str(event_id))

    assert result["blocked"] is True
    assert result["sent"] is False
    assert wamock.SENT == []  # nothing sent

    with tenant_session(DEMO_TENANT_ID) as s:
        events = s.scalars(
            select(GuardrailEvent).where(GuardrailEvent.type == "SCOPE")
        ).all()
        assert events and not events[0].action_taken == "PASSED"
        # No OUT message was queued/sent.
        out = s.scalar(select(func.count(Message.id)).where(Message.direction == "OUT"))
        assert out == 0
