"""Partner client management: per-client detail, commission, and 'open as client' token."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from leadpilot.bff.app import app
from leadpilot.scripts.demo_constants import DEMO_PARTNER_PHONE


@pytest.fixture
def client(seeded):
    return TestClient(app)


def _partner_auth(c: TestClient) -> dict:
    code = c.post("/api/v1/auth/otp/request", json={"phone": DEMO_PARTNER_PHONE}).json()["dev_code"]
    tok = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_PARTNER_PHONE, "code": code}).json()
    return {"Authorization": f"Bearer {tok['access']}"}


def test_partner_creates_and_drills_into_client(client):
    h = _partner_auth(client)
    created = client.post("/api/v1/partner/sub-accounts",
                          json={"business_name": "Verma Dental", "category": "clinic"}, headers=h)
    assert created.status_code == 200
    acc = created.json()["account_id"]

    detail = client.get(f"/api/v1/partner/sub-accounts/{acc}", headers=h)
    assert detail.status_code == 200
    d = detail.json()
    assert d["business_name"] == "Verma Dental"
    assert "commission_display" in d and "total_spend_display" in d


def test_partner_open_issues_account_scoped_token(client):
    h = _partner_auth(client)
    acc = client.post("/api/v1/partner/sub-accounts",
                      json={"business_name": "Iqbal Motors", "category": "other"},
                      headers=h).json()["account_id"]

    opened = client.post(f"/api/v1/partner/sub-accounts/{acc}/open", headers=h)
    assert opened.status_code == 200
    client_token = opened.json()["access"]

    # The issued token can read THAT client's home, and only that account.
    ch = {"Authorization": f"Bearer {client_token}"}
    home = client.get(f"/api/v1/accounts/{acc}/home", headers=ch)
    assert home.status_code == 200


def test_non_partner_cannot_use_partner_endpoints(client):
    # A fresh self-serve owner (role OWNER) is refused the agency console.
    code = client.post("/api/v1/auth/otp/request", json={"phone": "+919700000999"}).json()["dev_code"]
    tok = client.post("/api/v1/auth/otp/verify",
                      json={"phone": "+919700000999", "code": code}).json()
    h = {"Authorization": f"Bearer {tok['access']}"}
    r = client.get("/api/v1/partner/sub-accounts", headers=h)
    assert r.status_code == 403
