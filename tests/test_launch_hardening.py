"""Launch-hardening + remaining features: rate limiting, Embedded-Signup callback,
CSV export, Pro wallet, async pipeline triggers."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import leadpilot.bff.routers.agents as agents_router
from leadpilot.bff.app import app
from leadpilot.common.config import settings
from leadpilot.common.crypto import decrypt
from leadpilot.core.db import tenant_session
from leadpilot.core.models import Lead, MetaConnection
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID


@pytest.fixture
def client(seeded):
    return TestClient(app)


def _auth(c: TestClient) -> dict:
    code = c.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE}).json()["dev_code"]
    tok = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    return {"Authorization": f"Bearer {tok['access']}"}


def test_otp_request_rate_limited(client):
    phone = "+919999900000"  # fresh phone, unused elsewhere
    codes = [client.post("/api/v1/auth/otp/request", json={"phone": phone}).status_code
             for _ in range(5)]
    assert codes == [202, 202, 202, 202, 202]
    # 6th within the window is throttled.
    assert client.post("/api/v1/auth/otp/request", json={"phone": phone}).status_code == 429


def test_embedded_signup_stores_encrypted_token(client):
    h = _auth(client)
    r = client.post("/api/v1/onboarding/meta/embedded-signup/callback", headers=h, json={
        "code": "ES_CODE_123456", "ad_account_id": "act_555", "page_id": "page_555",
        "meta_business_id": "biz_1"})
    assert r.status_code == 200 and r.json()["ad_account_id"] == "act_555"
    with tenant_session(DEMO_TENANT_ID) as s:
        mc = s.scalar(select(MetaConnection).where(MetaConnection.account_id == DEMO_ACCOUNT_ID))
        assert mc.system_user_token_enc and mc.system_user_token_enc != ""
        assert decrypt(mc.system_user_token_enc).startswith("mock-system-user-token-")


def test_csv_export(client):
    h = _auth(client)
    with tenant_session(DEMO_TENANT_ID) as s:
        s.add(Lead(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID, wa_phone="+919800000777",
                   name="Test Lead", status="QUALIFIED_HOT", score="HOT",
                   intent_summary="wants coaching"))
    r = client.get(f"/api/v1/accounts/{DEMO_ACCOUNT_ID}/leads/export.csv", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    body = r.text
    assert "name,phone,score" in body and "Test Lead" in body and "+919800000777" in body


def test_wallet_topup_and_balance(client):
    h = _auth(client)
    r = client.post("/api/v1/billing/wallet/topup", headers=h, json={"amount_paise": 50000})
    assert r.json()["balance_paise"] == 50000
    r2 = client.post("/api/v1/billing/wallet/topup", headers=h, json={"amount_paise": 25000})
    assert r2.json()["balance_paise"] == 75000
    w = client.get("/api/v1/billing/wallet", headers=h).json()
    assert w["balance_paise"] == 75000 and len(w["ledger"]) == 2
    # Non-positive top-up rejected.
    assert client.post("/api/v1/billing/wallet/topup", headers=h,
                       json={"amount_paise": 0}).status_code == 422


def test_pipeline_async_enqueues(client, monkeypatch):
    h = _auth(client)
    monkeypatch.setattr(settings, "pipeline_inline", False)
    enqueue = MagicMock()
    monkeypatch.setattr(agents_router, "enqueue_pipeline", enqueue)
    r = client.post(f"/api/v1/accounts/{DEMO_ACCOUNT_ID}/research/run", headers=h)
    assert r.json() == {"status": "queued", "phase": "research"}
    assert enqueue.call_count == 1
