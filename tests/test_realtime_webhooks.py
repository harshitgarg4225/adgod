"""Real OTP flow + Razorpay billing webhook + Meta lead-form webhook + readiness."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import leadpilot.webhook.app as webhook_app
from leadpilot.bff.app import app as bff_app
from leadpilot.common.config import settings
from leadpilot.core.db import tenant_session
from leadpilot.core.models import AuthOtp, Invoice, Lead, Subscription
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID

# ───────────────────────── Real OTP ─────────────────────────

def test_real_otp_request_stores_and_verifies(seeded):
    c = TestClient(bff_app)
    r = c.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE})
    assert r.status_code == 202
    code = r.json()["dev_code"]
    # A hashed OTP row exists (never the plaintext).
    from leadpilot.core.db import platform_session

    with platform_session() as s:
        otp = s.scalar(select(AuthOtp).where(AuthOtp.phone == DEMO_OWNER_PHONE))
        assert otp and otp.code_hash != code

    bad = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": "999999"})
    assert bad.status_code == 401
    ok = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": code})
    assert ok.status_code == 200 and ok.json()["access"]
    # Consumed → cannot be reused.
    again = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": code})
    assert again.status_code == 401


# ───────────────────────── Razorpay webhook ─────────────────────────

@pytest.fixture
def razorpay_client(seeded, monkeypatch):
    monkeypatch.setattr(settings, "razorpay_webhook_secret", "rzp-secret")
    # Give the demo account a subscription to charge.
    with tenant_session(DEMO_TENANT_ID) as s:
        s.add(Subscription(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID, tier="GROWTH",
                           status="TRIAL", razorpay_subscription_id="sub_TEST123"))
    return TestClient(webhook_app.app)


def _rzp_sign(raw: bytes) -> str:
    return hmac.new(b"rzp-secret", raw, hashlib.sha256).hexdigest()


def test_razorpay_charge_activates_and_invoices(razorpay_client):
    c = razorpay_client
    payload = {"event": "subscription.charged",
               "payload": {"subscription": {"entity": {"id": "sub_TEST123",
                           "current_end": int(datetime.now(UTC).timestamp())}}}}
    raw = json.dumps(payload).encode()
    r = c.post("/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": _rzp_sign(raw)})
    assert r.status_code == 200
    with tenant_session(DEMO_TENANT_ID) as s:
        sub = s.scalar(select(Subscription).where(
            Subscription.razorpay_subscription_id == "sub_TEST123"))
        assert sub.status == "ACTIVE"
        inv = s.scalar(select(Invoice).where(Invoice.account_id == DEMO_ACCOUNT_ID))
        assert inv and inv.status == "PAID" and inv.gst_paise == 62982  # 18% of ₹3,499

    # Bad signature rejected.
    assert c.post("/webhooks/razorpay", content=raw,
                  headers={"X-Razorpay-Signature": "deadbeef"}).status_code == 403


def test_razorpay_payment_failed_marks_past_due(razorpay_client):
    c = razorpay_client
    payload = {"event": "payment.failed",
               "payload": {"subscription": {"entity": {"id": "sub_TEST123"}}}}
    raw = json.dumps(payload).encode()
    c.post("/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": _rzp_sign(raw)})
    with tenant_session(DEMO_TENANT_ID) as s:
        sub = s.scalar(select(Subscription).where(
            Subscription.razorpay_subscription_id == "sub_TEST123"))
        assert sub.status == "PAST_DUE"


# ───────────────────────── Meta lead-form webhook ─────────────────────────

def test_meta_leadgen_captures_lead(seeded, monkeypatch):
    # Demo account is seeded with a MetaConnection page_id "9876543210".
    monkeypatch.setattr(settings, "meta_app_secret", "meta-secret")
    c = TestClient(webhook_app.app)
    value = {"leadgen_id": "444001", "page_id": "9876543210", "form_id": "f1",
             "field_data": [{"name": "full_name", "values": ["Priya"]},
                            {"name": "phone_number", "values": ["+919800001234"]}]}
    payload = {"entry": [{"changes": [{"field": "leadgen", "value": value}]}]}
    raw = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"meta-secret", raw, hashlib.sha256).hexdigest()

    r = c.post("/webhooks/meta/leadgen", content=raw, headers={"X-Hub-Signature-256": sig})
    assert r.status_code == 200 and r.json()["accepted"] == 1
    with tenant_session(DEMO_TENANT_ID) as s:
        lead = s.scalar(select(Lead).where(Lead.wa_phone == "+919800001234"))
        assert lead and lead.name == "Priya" and lead.source_channel == "META_LEADFORM"

    # Replay is idempotent (same leadgen_id → no second lead).
    c.post("/webhooks/meta/leadgen", content=raw, headers={"X-Hub-Signature-256": sig})
    with tenant_session(DEMO_TENANT_ID) as s:
        n = s.scalar(select(func.count(Lead.id)).where(Lead.wa_phone == "+919800001234"))
        assert n == 1


def test_readiness_endpoint(seeded):
    c = TestClient(bff_app)
    body = c.get("/ready").json()
    assert "db" in body and body["db"] is True
