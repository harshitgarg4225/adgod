"""Manual client provisioning (the review-free agency / own-number path)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from leadpilot.bff.app import app
from leadpilot.common.crypto import decrypt
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.models import MetaConnection, WaRoute, WhatsAppConnection
from leadpilot.scripts.provision_client import provision_client


@pytest.fixture
def client(seeded):
    return TestClient(app)


def test_provision_own_number_needs_no_waba(client):
    out = provision_client(
        business_name="Verma Dental", category="clinic", city="Indore",
        owner_phone="+919812349999", daily_budget_rupees=500, language="hi",
        meta_business_id="1", ad_account_id="2", page_id="3", meta_token="EAAG-secret",
        wa_mode="APP_DESTINATION",
    )
    tid, aid = out["tenant_id"], out["account_id"]

    with tenant_session(tid) as s:
        wa = s.scalar(select(WhatsAppConnection).where(WhatsAppConnection.account_id == aid))
        assert wa.mode == "APP_DESTINATION" and wa.display_phone == "+919812349999"
        meta = s.scalar(select(MetaConnection).where(MetaConnection.account_id == aid))
        assert meta.status == "ACTIVE"
        assert decrypt(meta.system_user_token_enc) == "EAAG-secret"  # stored encrypted

    # APP_DESTINATION requires no routing key / WABA (review-free).
    with platform_session() as s:
        assert s.scalar(select(WaRoute).where(WaRoute.account_id == aid)) is None

    # The owner can log in immediately with phone OTP.
    code = client.post("/api/v1/auth/otp/request", json={"phone": "+919812349999"}).json()["dev_code"]
    tok = client.post("/api/v1/auth/otp/verify",
                      json={"phone": "+919812349999", "code": code}).json()
    assert tok["user"]["account_id"] == aid


def test_provision_cloud_mode_registers_route(client):
    out = provision_client(
        business_name="Iqbal Motors", category="other", city="Indore",
        owner_phone="+919812340000", wa_mode="CLOUD_API", phone_number_id="PN-777",
    )
    with platform_session() as s:
        route = s.scalar(select(WaRoute).where(WaRoute.phone_number_id == "PN-777"))
        assert route is not None and str(route.account_id) == out["account_id"]
