"""BFF owner surface over HTTP: login → see HOT lead → transcript → mark Won
(PRD §6.7, §9; v1 AC: 'owner sees the HOT lead in the inbox')."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from leadpilot.bff.app import app
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE
from leadpilot.scripts.simulate_inbound import SCRIPT, deliver


@pytest.fixture
def client(seeded):
    # Produce a real HOT lead through the Closer flow.
    for text in SCRIPT:
        deliver(text)
    return TestClient(app)


def _auth(client: TestClient) -> tuple[str, str]:
    r = client.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE})
    assert r.status_code == 202
    code = r.json()["dev_code"]
    r2 = client.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": code})
    assert r2.status_code == 200
    body = r2.json()
    return body["access"], body["user"]["account_id"]


def test_requires_auth(client):
    assert client.get(f"/api/v1/accounts/{DEMO_ACCOUNT_ID}/home").status_code == 401


def test_owner_sees_hot_lead_and_acts(client):
    token, account_id = _auth(client)
    assert account_id == str(DEMO_ACCOUNT_ID)
    h = {"Authorization": f"Bearer {token}"}

    home = client.get(f"/api/v1/accounts/{account_id}/home", headers=h).json()
    assert home["enquiries_today"] >= 1
    assert home["qualified_today"] >= 1

    leads = client.get(f"/api/v1/accounts/{account_id}/leads", headers=h).json()
    assert leads, "expected at least one lead"
    top = leads[0]
    assert top["score"] == "HOT"  # HOT sorts first

    detail = client.get(f"/api/v1/leads/{top['id']}", headers=h).json()
    assert detail["name"] == "Aman"
    assert len(detail["transcript"]) >= 2
    assert any(m["direction"] == "OUT" for m in detail["transcript"])

    patched = client.patch(
        f"/api/v1/leads/{top['id']}", headers=h, json={"owner_action": "WON", "status": "WON"}
    ).json()
    assert patched["status"] == "WON"
    assert patched["owner_action"] == "WON"

    notifs = client.get(f"/api/v1/accounts/{account_id}/notifications", headers=h).json()
    assert any(n["kind"] == "HOT_LEAD" for n in notifs)


def test_wrong_account_forbidden(client):
    token, _ = _auth(client)
    h = {"Authorization": f"Bearer {token}"}
    import uuid

    r = client.get(f"/api/v1/accounts/{uuid.uuid4()}/leads", headers=h)
    assert r.status_code == 403
