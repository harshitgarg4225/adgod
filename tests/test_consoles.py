"""Partner console + admin/ops back-office, with role enforcement (PRD §6.10, §6.11)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from leadpilot.bff.app import app
from leadpilot.core.db import platform_session
from leadpilot.core.models import AuditLog
from leadpilot.scripts.demo_constants import (
    DEMO_ACCOUNT_ID,
    DEMO_ADMIN_PHONE,
    DEMO_OWNER_PHONE,
    DEMO_PARTNER_PHONE,
)


@pytest.fixture
def client(seeded):
    return TestClient(app)


def _token(c: TestClient, phone: str) -> str:
    code = c.post("/api/v1/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    return c.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code}).json()["access"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_partner_manages_sub_accounts(client):
    h = _h(_token(client, DEMO_PARTNER_PHONE))
    created = client.post("/api/v1/partner/sub-accounts", headers=h, json={
        "business_name": "Verma Dental", "category": "clinic", "city": "Bhopal"}).json()
    assert created["account_id"]
    subs = client.get("/api/v1/partner/sub-accounts", headers=h).json()
    assert any(x["business_name"] == "Verma Dental" for x in subs)
    roll = client.get("/api/v1/partner/rollup", headers=h).json()
    assert roll["accounts"] >= 1


def test_admin_search_pause_impersonate_flags(client):
    h = _h(_token(client, DEMO_ADMIN_PHONE))

    found = client.get("/api/v1/admin/accounts", headers=h, params={"q": "Sharma"}).json()
    assert any(a["id"] == str(DEMO_ACCOUNT_ID) for a in found)

    paused = client.post(f"/api/v1/admin/accounts/{DEMO_ACCOUNT_ID}/pause", headers=h).json()
    assert paused["phase"] == "PAUSED"
    with platform_session() as s:
        assert s.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "account_pause")) >= 1

    imp = client.post(f"/api/v1/admin/impersonate/{DEMO_ACCOUNT_ID}", headers=h).json()
    assert imp["access"] and imp["impersonating"] == str(DEMO_ACCOUNT_ID)
    with platform_session() as s:
        assert s.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "impersonate")) >= 1

    assert client.post("/api/v1/admin/feature-flags", headers=h,
                       json={"key": "video_creatives", "enabled": True}).json()["enabled"] is True
    flags = client.get("/api/v1/admin/feature-flags", headers=h).json()
    assert any(f["key"] == "video_creatives" and f["enabled"] for f in flags)


def test_role_enforcement(client):
    owner = _h(_token(client, DEMO_OWNER_PHONE))
    # Owner cannot reach admin or partner surfaces.
    assert client.get("/api/v1/admin/accounts", headers=owner).status_code == 403
    assert client.get("/api/v1/partner/sub-accounts", headers=owner).status_code == 403

    partner = _h(_token(client, DEMO_PARTNER_PHONE))
    assert client.get("/api/v1/admin/accounts", headers=partner).status_code == 403
