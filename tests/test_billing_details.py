"""GSTIN capture, GST-compliant invoice document, and monthly-cap enforcement."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from leadpilot.bff.app import app
from leadpilot.core.db import tenant_session
from leadpilot.core.models import AdInsight, BusinessProfile, Invoice
from leadpilot.saathi.guardrails.spend import check_monthly_cap
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID


@pytest.fixture
def client(seeded):
    return TestClient(app)


def _auth(c: TestClient) -> dict:
    code = c.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE}).json()["dev_code"]
    tok = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    return {"Authorization": f"Bearer {tok['access']}"}


def test_check_monthly_cap_unit():
    assert check_monthly_cap(month_to_date_paise=100, monthly_cap_paise=None).ok
    assert check_monthly_cap(month_to_date_paise=100, monthly_cap_paise=500).ok
    assert not check_monthly_cap(month_to_date_paise=500, monthly_cap_paise=500).ok


def test_gstin_saves_and_returns(client):
    h = _auth(client)
    acc = str(DEMO_ACCOUNT_ID)
    r = client.patch(f"/api/v1/accounts/{acc}/settings",
                     json={"gstin": "22AAAAA0000A1Z5", "legal_name": "Sharma Classes Pvt Ltd"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["gstin"] == "22AAAAA0000A1Z5"
    assert body["legal_name"] == "Sharma Classes Pvt Ltd"
    assert "monthly_spend_display" in body


def test_invoice_document_renders_with_gst(client):
    h = _auth(client)
    client.patch(f"/api/v1/accounts/{DEMO_ACCOUNT_ID}/settings",
                 json={"gstin": "22AAAAA0000A1Z5"}, headers=h)
    with tenant_session(DEMO_TENANT_ID) as s:
        inv = Invoice(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                      amount_paise=99900, gst_paise=17982, status="PAID", period="2026-07")
        s.add(inv)
        s.flush()
        inv_id = str(inv.id)
    r = client.get(f"/api/v1/billing/invoices/{inv_id}/document", headers=h)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "22AAAAA0000A1Z5" in r.text
    assert "GST" in r.text


def test_launch_blocked_when_monthly_cap_reached(client):
    h = _auth(client)
    acc = str(DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        prof = s.scalar(select_profile(DEMO_ACCOUNT_ID))
        prof.monthly_cap_paise = 100000
        s.add(AdInsight(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID, level="ACCOUNT",
                        ref_id=DEMO_ACCOUNT_ID, date=datetime.now(UTC), spend_paise=100000))
    r = client.post(f"/api/v1/accounts/{acc}/campaigns/launch", headers=h)
    assert r.status_code == 422


def select_profile(account_id):
    from sqlalchemy import select

    return select(BusinessProfile).where(BusinessProfile.account_id == account_id)
