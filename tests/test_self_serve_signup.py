"""Self-serve signup: a verified but unknown phone becomes a new owner account in the
SIGNED_UP phase (no admin/seed needed). This is the activation entry point AND the fix
for the OTP user-enumeration leak (unknown numbers no longer 404)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from leadpilot.bff.app import app


@pytest.fixture
def client(seeded):
    return TestClient(app)


def _signup(client: TestClient, phone: str) -> dict:
    r = client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert r.status_code == 202
    code = r.json()["dev_code"]
    r2 = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert r2.status_code == 200
    return r2.json()


def test_unknown_phone_creates_owner_account(client):
    body = _signup(client, "+919811122233")
    assert body["access"]
    assert body["user"]["account_id"]
    assert body["user"]["role"] == "OWNER"

    # The new account starts in onboarding (SIGNED_UP) with all connection steps missing.
    h = {"Authorization": f"Bearer {body['access']}"}
    st = client.get("/api/v1/onboarding/status", headers=h)
    assert st.status_code == 200
    data = st.json()
    assert data["phase"] == "SIGNED_UP"
    assert set(data["missing_steps"]) == {
        "business_profile", "meta_connection", "whatsapp_connection"
    }


def test_signup_is_idempotent_per_phone(client):
    first = _signup(client, "+919844455566")
    second = _signup(client, "+919844455566")
    # Same phone logs back into the SAME account, never a duplicate.
    assert first["user"]["account_id"] == second["user"]["account_id"]


def test_new_tenant_is_isolated_from_demo(client):
    body = _signup(client, "+919877788899")
    h = {"Authorization": f"Bearer {body['access']}"}
    # The fresh owner sees zero leads — RLS keeps the seeded demo tenant's data invisible.
    acct = body["user"]["account_id"]
    leads = client.get(f"/api/v1/accounts/{acct}/leads", headers=h)
    assert leads.status_code == 200
    assert leads.json() == []
