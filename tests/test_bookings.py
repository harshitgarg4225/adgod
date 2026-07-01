"""Booking flow: owner turns a qualified lead into a scheduled appointment (the core
'fill my calendar' job that was entirely orphaned)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from leadpilot.bff.app import app
from leadpilot.core.db import tenant_session
from leadpilot.core.models import Lead
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID


@pytest.fixture
def client(seeded):
    return TestClient(app)


def _auth(c: TestClient) -> dict:
    code = c.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE}).json()["dev_code"]
    tok = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    return {"Authorization": f"Bearer {tok['access']}"}


def _make_lead() -> str:
    with tenant_session(DEMO_TENANT_ID) as s:
        lead = Lead(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                    source_channel="META_CTWA", wa_phone="+919812345678",
                    status="QUALIFIED_HOT", name="Rekha")
        s.add(lead)
        s.flush()
        return str(lead.id)


def test_book_lead_and_list(client):
    h = _auth(client)
    lead_id = _make_lead()

    r = client.post(f"/api/v1/leads/{lead_id}/book",
                    json={"slot_start": "2026-07-05T10:30:00+00:00"}, headers=h)
    assert r.status_code == 200
    booking = r.json()
    assert booking["status"] == "CONFIRMED"
    assert booking["lead_name"] == "Rekha"

    # Lead moved to BOOKED.
    lead = client.get(f"/api/v1/leads/{lead_id}", headers=h).json()
    assert lead["status"] == "BOOKED"

    # Appears in the account's bookings.
    lst = client.get(f"/api/v1/accounts/{DEMO_ACCOUNT_ID}/bookings", headers=h).json()
    assert any(b["id"] == booking["id"] for b in lst)


def test_book_is_idempotent_per_lead(client):
    h = _auth(client)
    lead_id = _make_lead()
    b1 = client.post(f"/api/v1/leads/{lead_id}/book", json={}, headers=h).json()
    b2 = client.post(f"/api/v1/leads/{lead_id}/book", json={}, headers=h).json()
    assert b1["id"] == b2["id"]  # reused, not duplicated


def test_cancel_booking(client):
    h = _auth(client)
    lead_id = _make_lead()
    booking = client.post(f"/api/v1/leads/{lead_id}/book", json={}, headers=h).json()
    r = client.patch(f"/api/v1/bookings/{booking['id']}", json={"status": "CANCELLED"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"


def test_cannot_book_other_tenants_lead(client):
    """A second owner cannot book a lead in the demo tenant (RLS + access guard)."""
    h2 = None
    # Sign up a fresh owner in a different tenant.
    code = client.post("/api/v1/auth/otp/request", json={"phone": "+919700000123"}).json()["dev_code"]
    tok = client.post("/api/v1/auth/otp/verify",
                      json={"phone": "+919700000123", "code": code}).json()
    h2 = {"Authorization": f"Bearer {tok['access']}"}
    lead_id = _make_lead()  # belongs to the demo tenant
    r = client.post(f"/api/v1/leads/{lead_id}/book", json={}, headers=h2)
    assert r.status_code in (403, 404)  # not visible / not allowed
