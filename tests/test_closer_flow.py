"""End-to-end Closer qualification (PRD §6.6; v1 AC)."""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict

from sqlalchemy import func, select

import leadpilot.integrations.whatsapp.mock as wamock
from leadpilot.core.db import tenant_session
from leadpilot.core.models import AgentRun, Lead, LeadQualification, Message, Notification
from leadpilot.core.routing import record_inbound_event
from leadpilot.integrations.whatsapp.base import InboundMessage
from leadpilot.scripts.demo_constants import (
    DEMO_ACCOUNT_ID,
    DEMO_PHONE_NUMBER_ID,
    DEMO_TENANT_ID,
)
from leadpilot.scripts.simulate_inbound import SCRIPT
from leadpilot.worker.tasks.closer import run_inbound


def _deliver(text: str, phone: str) -> dict:
    inbound = InboundMessage(
        wa_message_id="wamid." + uuid.uuid4().hex, from_phone=phone,
        phone_number_id=DEMO_PHONE_NUMBER_ID, text=text,
    )
    event_id = record_inbound_event(
        provider="whatsapp", external_id=inbound.wa_message_id,
        tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
        payload={"message": asdict(inbound)},
    )
    return run_inbound(str(event_id))


def test_full_conversation_qualifies_hot(seeded):
    wamock.SENT.clear()
    phone = "+919800000100"
    results = [_deliver(t, phone) for t in SCRIPT]

    assert results[-1]["score"] == "HOT"
    assert results[-1]["hot"] is True
    assert all(r["sent"] for r in results)

    with tenant_session(DEMO_TENANT_ID) as s:
        lead = s.scalar(select(Lead).where(Lead.wa_phone == phone))
        assert lead.status == "QUALIFIED_HOT"
        assert lead.score == "HOT"
        assert lead.name == "Aman"
        assert lead.intent_summary and lead.location_signal
        assert lead.qualified_at is not None

        qual = s.scalar(select(LeadQualification).where(LeadQualification.lead_id == lead.id))
        assert qual is not None and qual.score == "HOT" and qual.reasons

        # One agent_run per turn, with model + token accounting.
        runs = s.scalars(select(AgentRun).where(AgentRun.account_id == DEMO_ACCOUNT_ID)).all()
        assert len(runs) == len(SCRIPT)
        assert all(r.agent == "CLOSER" and r.model for r in runs)

        # Hot-lead notification raised.
        notif = s.scalar(
            select(Notification).where(Notification.kind == "HOT_LEAD")
        )
        assert notif is not None

        # All five Saathi replies were actually "sent" (outbox drained).
        out_sent = s.scalar(
            select(func.count(Message.id)).where(
                Message.direction == "OUT", Message.status == "SENT"
            )
        )
        assert out_sent == len(SCRIPT)


def test_inbound_p95_under_5s(seeded):
    """50 fresh inbound greetings; p95 closer latency < 5s on the mock hot path."""
    wamock.SENT.clear()
    durations = []
    for i in range(50):
        phone = f"+9198000{i:05d}"
        start = time.perf_counter()
        _deliver("Hello, info chahiye", phone)
        durations.append(time.perf_counter() - start)
    durations.sort()
    p95 = durations[int(0.95 * len(durations)) - 1]
    assert p95 < 5.0, f"p95={p95:.3f}s"
