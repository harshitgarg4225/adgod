"""Owner in-app WhatsApp reply + out-of-window re-engagement templates."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from leadpilot.bff.app import app
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.models import Conversation, Lead, Message, OutboxEntry
from leadpilot.saathi.workflow import get_workflow_runner
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID
from leadpilot.worker.tasks.maintenance import re_engage


@pytest.fixture
def client(seeded):
    return TestClient(app)


def _auth(c: TestClient) -> dict:
    code = c.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE}).json()["dev_code"]
    tok = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    return {"Authorization": f"Bearer {tok['access']}"}


def _lead_with_conversation(window_open: bool) -> str:
    with tenant_session(DEMO_TENANT_ID) as s:
        lead = Lead(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                    source_channel="META_CTWA", wa_phone="+919820011122", status="ENGAGED")
        s.add(lead)
        s.flush()
        expiry = datetime.now(UTC) + timedelta(hours=5 if window_open else -1)
        s.add(Conversation(tenant_id=DEMO_TENANT_ID, lead_id=lead.id, channel="WHATSAPP",
                           state="SCORE", free_window_expires_at=expiry))
        return str(lead.id)


def test_owner_reply_within_window_queues_send(client):
    h = _auth(client)
    lead_id = _lead_with_conversation(window_open=True)
    r = client.post(f"/api/v1/leads/{lead_id}/message", json={"text": "Hi, calling you now!"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "queued"

    # Drain the outbox → the mock adapter marks the message SENT.
    get_workflow_runner().drain_until_empty()
    with tenant_session(DEMO_TENANT_ID) as s:
        msg = s.get(Message, r.json()["message_id"])
        assert msg.direction == "OUT" and msg.status == "SENT"


def test_owner_reply_blocked_outside_window(client):
    h = _auth(client)
    lead_id = _lead_with_conversation(window_open=False)
    r = client.post(f"/api/v1/leads/{lead_id}/message", json={"text": "hello?"}, headers=h)
    assert r.status_code == 422  # window closed → asked to call instead


def test_re_engage_sends_one_template_to_silent_lead(client):
    lead_id = _lead_with_conversation(window_open=False)
    with tenant_session(DEMO_TENANT_ID) as s:
        s.get(Lead, lead_id).status = "NO_RESPONSE"

    assert re_engage()["sent"] == 1
    # A TEMPLATE message was queued through the outbox.
    with tenant_session(DEMO_TENANT_ID) as s:
        tmpl = s.query(Message).filter(
            Message.type == "TEMPLATE", Message.template_name == "re_engagement"
        ).all()
        assert len(tmpl) == 1

    # Idempotent: a second run does not re-send.
    assert re_engage()["sent"] == 0


def test_seeded_templates_exist(client):
    with platform_session() as s:
        from leadpilot.core.models import WaTemplate

        names = {t.name for t in s.query(WaTemplate).all()}
        assert {"re_engagement", "daily_summary", "welcome"} <= names
    # keep OutboxEntry import used (drain path exercised elsewhere)
    assert OutboxEntry is not None
