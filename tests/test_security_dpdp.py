"""JWT revocation (logout / delete), DPDP export+erasure, OTP salt, tenant-scoped
idempotency, and wa_route hijack protection."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from leadpilot.bff.app import app
from leadpilot.core.db import platform_session
from leadpilot.core.idempotency import lookup, store
from leadpilot.core.models import AuthOtp
from leadpilot.scripts.demo_constants import DEMO_OWNER_PHONE


@pytest.fixture
def client(seeded):
    return TestClient(app)


def _auth(c: TestClient, phone: str = DEMO_OWNER_PHONE) -> dict:
    code = c.post("/api/v1/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    tok = c.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code}).json()
    return {"Authorization": f"Bearer {tok['access']}", "_acc": tok["user"]["account_id"]}


def test_logout_revokes_outstanding_token(client):
    h = _auth(client)
    acc = h["_acc"]
    hh = {"Authorization": h["Authorization"]}
    assert client.get(f"/api/v1/accounts/{acc}/home", headers=hh).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=hh).status_code == 200
    # Same token is now rejected (token_version bumped).
    assert client.get(f"/api/v1/accounts/{acc}/home", headers=hh).status_code == 401


def test_dpdp_export_and_delete(client):
    h = _auth(client, "+919701234567")
    hh = {"Authorization": h["Authorization"]}
    exp = client.get("/api/v1/auth/me/export", headers=hh)
    assert exp.status_code == 200 and "user" in exp.json()

    assert client.request("DELETE", "/api/v1/auth/me", headers=hh).status_code == 200
    # Token revoked + user soft-deleted → further calls rejected.
    assert client.get("/api/v1/auth/me/export", headers=hh).status_code == 401


def test_otp_uses_per_row_salt(client):
    client.post("/api/v1/auth/otp/request", json={"phone": "+919788888888"})
    with platform_session() as s:
        otp = s.query(AuthOtp).filter(AuthOtp.phone == "+919788888888").first()
        assert otp.salt and len(otp.salt) >= 16


def test_idempotency_keys_are_tenant_scoped(seeded):
    # Same key, two tenants → independent stores, no collision, no cross-tenant read.
    t1 = "11111111-1111-1111-1111-111111111111"
    t2 = "22222222-2222-2222-2222-222222222222"
    with platform_session() as s:
        store(s, key="k1", request_hash="h", response_code=200,
              response_body={"who": "t1"}, tenant_id=t1)
        store(s, key="k1", request_hash="h", response_code=200,
              response_body={"who": "t2"}, tenant_id=t2)
    with platform_session() as s:
        assert lookup(s, "k1", tenant_id=t1)["response_body"]["who"] == "t1"
        assert lookup(s, "k1", tenant_id=t2)["response_body"]["who"] == "t2"


def test_wa_route_hijack_is_refused(client):
    """A second tenant cannot claim a phone_number_id already routed to another tenant."""
    # The seeded demo already routes DEMO_PHONE_NUMBER_ID to the demo tenant.
    from leadpilot.scripts.demo_constants import DEMO_PHONE_NUMBER_ID

    h = _auth(client, "+919755555555")  # fresh tenant/owner
    hh = {"Authorization": h["Authorization"]}
    r = client.post(
        "/api/v1/onboarding/whatsapp/connect",
        json={"mode": "CLOUD_API", "phone_number_id": DEMO_PHONE_NUMBER_ID},
        headers=hh,
    )
    assert r.status_code == 422  # refused — belongs to another tenant
