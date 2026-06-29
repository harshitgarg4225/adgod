"""Webhook intake: signature + idempotency + enqueue (PRD §9.4, §10.2; v1 AC)."""
from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import leadpilot.webhook.app as webhook_app
from leadpilot.common.config import settings
from leadpilot.core.db import engine
from leadpilot.scripts.demo_constants import DEMO_LEAD_PHONE, DEMO_PHONE_NUMBER_ID

SECRET = "test-app-secret"


@pytest.fixture
def client(seeded, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_app_secret", SECRET)
    monkeypatch.setattr(settings, "whatsapp_webhook_verify_token", "verify-tok")
    enqueue = MagicMock()
    monkeypatch.setattr(webhook_app, "enqueue_closer", enqueue)
    return TestClient(webhook_app.app), enqueue


def _payload(wa_message_id: str, text_body: str = "hi") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "+919876500000",
                                 "phone_number_id": DEMO_PHONE_NUMBER_ID},
                    "messages": [{
                        "from": DEMO_LEAD_PHONE.lstrip("+"),
                        "id": wa_message_id,
                        "timestamp": "1700000000",
                        "type": "text",
                        "text": {"body": text_body},
                    }],
                },
            }],
        }],
    }


def _sign(raw: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()


def _count_inbound() -> int:
    with engine.begin() as conn:
        return conn.execute(text("SELECT count(*) FROM inbound_events")).scalar_one()


def test_verify_handshake(client):
    c, _ = client
    r = c.get("/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "verify-tok", "hub.challenge": "42",
    })
    assert r.status_code == 200 and r.text == "42"
    bad = c.get("/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "42",
    })
    assert bad.status_code == 403


def test_valid_signature_persists_once_and_enqueues_once(client):
    c, enqueue = client
    raw = json.dumps(_payload("wamid.AAA")).encode()
    r = c.post("/webhooks/whatsapp", content=raw, headers={"X-Hub-Signature-256": _sign(raw)})
    assert r.status_code == 200 and r.json()["accepted"] == 1
    assert _count_inbound() == 1
    assert enqueue.call_count == 1


def test_replay_is_idempotent(client):
    c, enqueue = client
    raw = json.dumps(_payload("wamid.DUP")).encode()
    sig = _sign(raw)
    c.post("/webhooks/whatsapp", content=raw, headers={"X-Hub-Signature-256": sig})
    # Same wa_message_id again:
    r2 = c.post("/webhooks/whatsapp", content=raw, headers={"X-Hub-Signature-256": sig})
    assert r2.status_code == 200
    assert _count_inbound() == 1            # no new row
    assert enqueue.call_count == 1          # no new enqueue


def test_invalid_signature_rejected_and_persists_nothing(client):
    c, enqueue = client
    raw = json.dumps(_payload("wamid.BAD")).encode()
    r = c.post("/webhooks/whatsapp", content=raw,
               headers={"X-Hub-Signature-256": "sha256=deadbeef"})
    assert r.status_code == 403
    assert _count_inbound() == 0
    assert enqueue.call_count == 0

    # Missing signature too.
    r2 = c.post("/webhooks/whatsapp", content=raw)
    assert r2.status_code == 403
    assert _count_inbound() == 0
