"""Outbound HTTP retry/breaker, Closer degraded fallback, streaming CSV, embedded signup."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from leadpilot.bff.app import app
from leadpilot.common.http_retry import CircuitBreaker, parse_retry_after, request_with_retry
from leadpilot.core.db import tenant_session
from leadpilot.core.models import Conversation, Lead, Message
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID


class _Resp:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


def test_parse_retry_after_seconds():
    assert parse_retry_after("5") == 5.0
    assert parse_retry_after(None) is None


def test_request_with_retry_recovers_after_429():
    calls = []

    def do():
        calls.append(1)
        return _Resp(429 if len(calls) < 3 else 200, {"Retry-After": "0"})

    resp = request_with_retry(do, max_attempts=5, sleep=lambda _s: None)
    assert resp.status_code == 200
    assert len(calls) == 3


def test_request_with_retry_gives_up_and_returns_last():
    resp = request_with_retry(lambda: _Resp(503), max_attempts=2, sleep=lambda _s: None)
    assert resp.status_code == 503


def test_circuit_breaker_opens_and_half_opens():
    clock = {"t": 0.0}
    cb = CircuitBreaker(threshold=2, cooldown=10, now=lambda: clock["t"])
    assert not cb.is_open
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open  # tripped
    clock["t"] = 11
    assert not cb.is_open  # half-open after cooldown
    cb.record_success()
    assert not cb.is_open


@pytest.fixture
def client(seeded):
    return TestClient(app)


def _auth(c: TestClient) -> dict:
    code = c.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE}).json()["dev_code"]
    tok = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    return {"Authorization": f"Bearer {tok['access']}"}


def test_closer_degrades_to_handoff_when_llm_fails(client, monkeypatch):
    from leadpilot.scripts.simulate_inbound import deliver

    def boom(*_a, **_k):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("leadpilot.saathi.agents.closer.CloserAgent.run", boom)
    result = deliver("Hello, do you offer NEET coaching?")
    assert result  # did not raise

    with tenant_session(DEMO_TENANT_ID) as s:
        lead = s.scalar(select_lead())
        assert lead.status == "HANDED_OFF"
        conv = s.scalar(select_conv(lead.id))
        assert conv.state == "HANDOFF"
        # A safe canned reply was queued to the lead (Hindi or English).
        out = s.query(Message).filter(
            Message.conversation_id == conv.id, Message.direction == "OUT"
        ).all()
        assert any((m.body or "").strip() for m in out)


def test_export_csv_streams(client):
    h = _auth(client)
    with tenant_session(DEMO_TENANT_ID) as s:
        s.add(Lead(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                   source_channel="META_CTWA", wa_phone="+919812300000",
                   name="Nisha", status="QUALIFIED_HOT"))
    r = client.get(f"/api/v1/accounts/{DEMO_ACCOUNT_ID}/leads/export.csv", headers=h)
    assert r.status_code == 200
    assert "name,phone,score" in r.text
    assert "Nisha" in r.text


def test_embedded_signup_start_dev(client):
    h = _auth(client)
    r = client.get("/api/v1/onboarding/meta/embedded-signup/start", headers=h)
    assert r.status_code == 200
    # No Meta app id configured in dev → UI falls back to manual connect.
    assert r.json()["configured"] is False


def select_lead():
    from sqlalchemy import select

    return select(Lead).where(Lead.account_id == DEMO_ACCOUNT_ID).order_by(Lead.created_at.desc())


def select_conv(lead_id):
    from sqlalchemy import select

    return select(Conversation).where(Conversation.lead_id == lead_id)
