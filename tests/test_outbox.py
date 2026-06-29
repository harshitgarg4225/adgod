"""Transactional outbox: exactly-once effect + DLQ on exhaustion (PRD §7.4; v1 AC)."""
from __future__ import annotations

import uuid

from sqlalchemy import text

import leadpilot.integrations.whatsapp.mock as wamock
from leadpilot.core.db import engine, tenant_session
from leadpilot.core.models import Conversation, Lead, Message
from leadpilot.core.outbox import enqueue_effect, mark_retry
from leadpilot.saathi.workflow.effects import handle_whatsapp_send
from leadpilot.saathi.workflow.runner import WorkflowRunner
from leadpilot.scripts.demo_constants import (
    DEMO_ACCOUNT_ID,
    DEMO_LEAD_PHONE,
    DEMO_PHONE_NUMBER_ID,
    DEMO_TENANT_ID,
)


def _queue_a_send(step_id: str) -> tuple[uuid.UUID, dict]:
    with tenant_session(DEMO_TENANT_ID) as s:
        lead = Lead(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                    wa_phone=DEMO_LEAD_PHONE, status="ENGAGED")
        s.add(lead)
        s.flush()
        conv = Conversation(tenant_id=DEMO_TENANT_ID, lead_id=lead.id, state="GREET")
        s.add(conv)
        s.flush()
        msg = Message(tenant_id=DEMO_TENANT_ID, conversation_id=conv.id, direction="OUT",
                      body="Namaste!", status="QUEUED")
        s.add(msg)
        s.flush()
        payload = {
            "message_id": str(msg.id), "phone_number_id": DEMO_PHONE_NUMBER_ID,
            "to_phone": DEMO_LEAD_PHONE, "kind": "text", "body": "Namaste!", "buttons": [],
        }
        enqueue_effect(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                       step_id=step_id, effect_type="whatsapp_send", payload=payload)
        return msg.id, payload


def _msg_status(message_id: uuid.UUID) -> str:
    with tenant_session(DEMO_TENANT_ID) as s:
        return s.get(Message, message_id).status


def test_exactly_once_effect(seeded):
    wamock.SENT.clear()
    message_id, payload = _queue_a_send("step-1:reply")

    WorkflowRunner().drain_until_empty()
    assert len(wamock.SENT) == 1               # sent exactly once
    assert _msg_status(message_id) == "SENT"

    # Re-running the same step (e.g., a redelivery) must NOT send again.
    res = handle_whatsapp_send({"tenant_id": DEMO_TENANT_ID, "payload": payload, "attempts": 0})
    assert res.get("idempotent") is True
    assert len(wamock.SENT) == 1               # still exactly once


def test_duplicate_enqueue_is_noop(seeded):
    wamock.SENT.clear()
    _queue_a_send("dup-step:reply")
    # Same (account_id, step_id) again — ON CONFLICT DO NOTHING.
    _queue_a_send("dup-step:reply")
    with engine.begin() as conn:
        n = conn.execute(
            text("SELECT count(*) FROM outbox WHERE step_id = 'dup-step:reply'")
        ).scalar_one()
    assert n == 1


def test_failure_exhaustion_lands_in_dlq(seeded):
    message_id, _ = _queue_a_send("dead-step:reply")
    with engine.begin() as conn:
        entry_id = conn.execute(
            text("SELECT id, attempts FROM outbox WHERE step_id='dead-step:reply'")
        ).first()
    # Drive attempts to exhaustion → DEAD + a dlq row.
    from leadpilot.core.outbox import MAX_ATTEMPTS

    with tenant_session(DEMO_TENANT_ID) as s:
        for attempt in range(MAX_ATTEMPTS):
            mark_retry(s, entry_id[0], attempt, "boom")
    with engine.begin() as conn:
        status = conn.execute(
            text("SELECT status FROM outbox WHERE id=:id"), {"id": str(entry_id[0])}
        ).scalar_one()
        dlq = conn.execute(text("SELECT count(*) FROM dlq")).scalar_one()
    assert status == "DEAD"
    assert dlq == 1
