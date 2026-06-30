"""CTWA-to-app go-live flow: connect WhatsApp number + Meta, then launch a real-shaped
CTWA campaign whose destination is the owner's WhatsApp number (PRD §6.1.3)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from leadpilot.bff.app import app
from leadpilot.common.crypto import decrypt
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.models import Account, MetaConnection, WaRoute, WhatsAppConnection
from leadpilot.saathi import pipeline
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID


def test_token_encryption_roundtrip():
    from leadpilot.common.crypto import encrypt

    enc = encrypt("EAA-meta-system-user-token")
    assert enc != "EAA-meta-system-user-token"
    assert decrypt(enc) == "EAA-meta-system-user-token"
    assert decrypt(None) is None


@pytest.fixture
def auth(seeded):
    # Fresh account with no connections, owner autopilot FULL for a clean launch.
    with tenant_session(DEMO_TENANT_ID) as s:
        acc = s.get(Account, DEMO_ACCOUNT_ID)
        acc.autopilot_level = "FULL"
        for conn in s.scalars(
            select(WhatsAppConnection).where(WhatsAppConnection.account_id == DEMO_ACCOUNT_ID)
        ).all():
            s.delete(conn)
    c = TestClient(app)
    code = c.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE}).json()["dev_code"]
    tok = c.post("/api/v1/auth/otp/verify", json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    return c, {"Authorization": f"Bearer {tok['access']}"}


def test_app_destination_connect_and_launch(auth):
    c, h = auth

    # Connect the owner's existing WhatsApp number (no API / WABA needed).
    r = c.post("/api/v1/onboarding/whatsapp/connect", headers=h,
               json={"mode": "APP_DESTINATION", "phone": "+919811111111"})
    assert r.status_code == 200
    assert r.json() == {"mode": "APP_DESTINATION", "closer_enabled": False}

    # Connect Meta ad account/Page with a system-user token (stored encrypted).
    r2 = c.post("/api/v1/onboarding/meta/connect", headers=h, json={
        "meta_business_id": "111", "ad_account_id": "act_999", "page_id": "page_999",
        "system_user_token": "EAA-secret"})
    assert r2.status_code == 200
    with tenant_session(DEMO_TENANT_ID) as s:
        mc = s.scalar(select(MetaConnection).where(MetaConnection.account_id == DEMO_ACCOUNT_ID))
        assert mc.ad_account_id == "act_999"
        assert mc.system_user_token_enc and mc.system_user_token_enc != "EAA-secret"
        assert decrypt(mc.system_user_token_enc) == "EAA-secret"  # decryptable, encrypted at rest

    # Run the pipeline → a real-shaped CTWA campaign goes live to the owner's number.
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        ids = pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    assert ids
    assert c.get(f"/api/v1/accounts/{DEMO_ACCOUNT_ID}/campaigns", headers=h).json()


def test_cloud_api_connect_registers_route(auth):
    c, h = auth
    r = c.post("/api/v1/onboarding/whatsapp/connect", headers=h,
               json={"mode": "CLOUD_API", "phone_number_id": "555000111", "waba_id": "waba_1"})
    assert r.json() == {"mode": "CLOUD_API", "closer_enabled": True}
    # A routing row is registered so inbound webhooks resolve the tenant.
    with platform_session() as s:
        route = s.scalar(select(WaRoute).where(WaRoute.phone_number_id == "555000111"))
        assert route and str(route.account_id) == str(DEMO_ACCOUNT_ID)
