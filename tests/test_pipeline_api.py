"""Owner drives Saathi through the BFF: onboard → research → creatives → launch →
optimize → report, plus billing (PRD §9.1–9.3, §9.6)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from leadpilot.bff.app import app
from leadpilot.core.db import tenant_session
from leadpilot.core.models import Account
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID


@pytest.fixture
def auth(seeded):
    with tenant_session(DEMO_TENANT_ID) as s:
        s.get(Account, DEMO_ACCOUNT_ID).autopilot_level = "FULL"
    c = TestClient(app)
    code = c.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE}).json()["dev_code"]
    body = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    return c, body["access"], body["user"]["account_id"]


def test_owner_drives_full_pipeline(auth):
    c, token, account_id = auth
    h = {"Authorization": f"Bearer {token}"}

    assert c.post("/api/v1/onboarding/business", headers=h, json={
        "business_name": "Sharma NEET Classes", "category": "coaching",
        "offer": "NEET coaching, small batches", "city": "Indore",
        "radius_km": 10, "daily_budget_paise": 50000, "language": "hi",
    }).status_code == 200

    assert c.post(f"/api/v1/accounts/{account_id}/research/run", headers=h).json()["brief_id"]
    assert c.get(f"/api/v1/accounts/{account_id}/brief", headers=h).json()["offer"]
    assert len(c.get(f"/api/v1/accounts/{account_id}/angles", headers=h).json()) >= 8

    creatives = c.post(f"/api/v1/accounts/{account_id}/creatives/generate", headers=h).json()
    assert creatives["creative_ids"]
    listed = c.get(f"/api/v1/accounts/{account_id}/creatives", headers=h).json()
    assert listed and listed[0]["asset_url"]

    launched = c.post(f"/api/v1/accounts/{account_id}/campaigns/launch", headers=h).json()
    assert launched["campaign_ids"]
    camps = c.get(f"/api/v1/accounts/{account_id}/campaigns", headers=h).json()
    assert any(x["status"] == "ACTIVE" for x in camps)

    opt = c.post(f"/api/v1/accounts/{account_id}/optimize/run", headers=h).json()
    assert opt["decisions"]
    assert c.get(f"/api/v1/accounts/{account_id}/insights", headers=h).json()
    assert c.get(f"/api/v1/accounts/{account_id}/optimization/decisions", headers=h).json()

    rep = c.post(f"/api/v1/accounts/{account_id}/report/run", headers=h).json()
    assert rep["message"]


def test_billing_tiers_and_subscribe(auth):
    c, token, _ = auth
    h = {"Authorization": f"Bearer {token}"}

    tiers = c.get("/api/v1/billing/tiers", headers=h).json()
    assert {t["tier"] for t in tiers} == {"STARTER", "GROWTH", "PRO"}
    growth = next(t for t in tiers if t["tier"] == "GROWTH")
    # ₹3,499 + 18% GST, all integer paise.
    assert growth["price_paise"] == 349900
    assert growth["gst_paise"] == 62982
    assert growth["total_paise"] == 412882

    sub = c.post("/api/v1/billing/subscribe", headers=h, json={"tier": "GROWTH"}).json()
    assert sub["mandate_url"] and sub["razorpay_subscription_id"].startswith("sub_")
    assert sub["total_paise"] == 412882

    current = c.get("/api/v1/billing/subscription", headers=h).json()
    assert current["tier"] == "GROWTH" and current["status"] == "TRIAL"
