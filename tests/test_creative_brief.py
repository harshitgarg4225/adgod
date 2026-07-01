"""Budget/timeline split + owner editing of brief, angles, and creatives."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from leadpilot.bff.app import app
from leadpilot.saathi.providers.mock_llm import _split_budget_timeline
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE


@pytest.fixture
def client(seeded):
    return TestClient(app)


def _auth(c: TestClient) -> dict:
    code = c.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE}).json()["dev_code"]
    tok = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    return {"Authorization": f"Bearer {tok['access']}"}


def test_split_budget_timeline_separates_signals():
    b, tl = _split_budget_timeline("around 50000 budget, want to start this month")
    assert b and "50000" in b
    assert tl and "month" in tl.lower()

    # Timeline-only answer (interactive button) → no fake budget.
    b2, tl2 = _split_budget_timeline("soon")
    assert b2 is None and tl2 == "soon"

    # Budget-only.
    b3, tl3 = _split_budget_timeline("₹2 lakh")
    assert b3 and tl3 is None


def test_owner_can_edit_brief_and_toggle_angle(client):
    h = _auth(client)
    acc = str(DEMO_ACCOUNT_ID)
    # Generate a brief + angles.
    client.post(f"/api/v1/accounts/{acc}/research/run", headers=h)

    r = client.patch(f"/api/v1/accounts/{acc}/brief",
                     json={"offer": "Corrected offer text"}, headers=h)
    assert r.status_code == 200 and r.json()["offer"] == "Corrected offer text"

    angles = client.get(f"/api/v1/accounts/{acc}/angles", headers=h).json()
    assert angles
    aid = angles[0]["id"]
    pr = client.patch(f"/api/v1/angles/{aid}", json={"status": "PAUSED"}, headers=h)
    assert pr.status_code == 200 and pr.json()["status"] == "PAUSED"


def test_owner_can_reject_creative(client):
    h = _auth(client)
    acc = str(DEMO_ACCOUNT_ID)
    client.post(f"/api/v1/accounts/{acc}/research/run", headers=h)
    client.post(f"/api/v1/accounts/{acc}/creatives/generate", headers=h)
    creatives = client.get(f"/api/v1/accounts/{acc}/creatives", headers=h).json()
    assert creatives
    cid = creatives[0]["id"]
    r = client.post(f"/api/v1/creatives/{cid}/reject", headers=h)
    assert r.status_code == 200 and r.json()["ok"] is True
    after = client.get(f"/api/v1/accounts/{acc}/creatives", headers=h).json()
    assert next(c for c in after if c["id"] == cid)["approval_status"] == "REJECTED"
