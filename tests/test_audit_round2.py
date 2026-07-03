"""Round-2 audit fixes: env fail-closed posture, minted-code login, Meta throttle-aware
retry, account-budget cap, live budget reconcile, admin fleet/digest/mark-paid, and
token redaction."""
from __future__ import annotations

from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from leadpilot.bff.app import app
from leadpilot.common.auth import issue_access_token
from leadpilot.common.config import Settings
from leadpilot.common.http_retry import request_with_retry
from leadpilot.common.logging import redact_text
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.enums import CampaignStatus
from leadpilot.core.models import AdSet, BusinessProfile, Creative, Subscription
from leadpilot.saathi import pipeline
from leadpilot.saathi.pipeline import _cap_to_account_budget
from leadpilot.scripts.create_admin import create_admin
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID
from leadpilot.scripts.mint_login import mint_login


def test_unknown_environment_gets_production_posture():
    # A typo'd ENVIRONMENT must never boot with dev-default secrets or wildcard CORS.
    for env in ("prod", "staging", "", "Production "):
        assert Settings(environment=env.strip() or "unknown").is_production, env
    for env in ("development", "dev", "test", "local"):
        assert not Settings(environment=env).is_production, env


def test_minted_code_survives_a_later_sms_request(seeded):
    """The operator mints a code, THEN the client taps 'Send OTP' — the minted code must
    still verify (it used to be superseded by the newest row)."""
    phone, minted = mint_login(DEMO_OWNER_PHONE)
    client = TestClient(app)
    client.post("/api/v1/auth/otp/request", json={"phone": phone})  # newer row lands
    r = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": minted})
    assert r.status_code == 200 and r.json()["access"]


def _resp(status: int, body: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=body or {},
                          request=httpx.Request("GET", "https://graph.facebook.com/x"))


def test_meta_throttle_400_is_retried():
    calls = {"n": 0}

    def do_request():
        calls["n"] += 1
        if calls["n"] == 1:
            return _resp(400, {"error": {"code": 4, "message": "App rate limit"}})
        return _resp(200, {"ok": True})

    out = request_with_retry(do_request, sleep=lambda _s: None)
    assert out.status_code == 200 and calls["n"] == 2


def test_transport_error_is_retried_not_fatal():
    calls = {"n": 0}

    def do_request():
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom")
        return _resp(200)

    out = request_with_retry(do_request, sleep=lambda _s: None)
    assert out.status_code == 200 and calls["n"] == 2


def test_scale_is_capped_at_account_daily_budget():
    a1 = SimpleNamespace(budget_paise=65000, status="ACTIVE")
    a2 = SimpleNamespace(budget_paise=20000, status="ACTIVE")
    # a1 wants +20% (78000) but the account budget is 100000 → only 80000 - 0 headroom:
    capped = _cap_to_account_budget([a1, a2], a1, 78000, 100000)
    assert capped == 78000  # 78000 + 20000 = 98000 ≤ 100000 → allowed
    capped = _cap_to_account_budget([a1, a2], a1, 90000, 100000)
    assert capped == 80000  # clamped so the total never exceeds the account budget
    # No headroom at all → stays at current (never force-shrinks here).
    a3 = SimpleNamespace(budget_paise=40000, status="ACTIVE")
    assert _cap_to_account_budget([a1, a3], a1, 90000, 100000) == 65000


def test_budget_patch_reconciles_live_adset_budgets(seeded):
    # Get the demo account LIVE first.
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        for c in s.scalars(select(Creative).where(
                Creative.account_id == DEMO_ACCOUNT_ID)).all():
            if c.compliance_status == "PASSED":
                c.approval_status = "APPROVED_FOR_LAUNCH"
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)

    # Owner cuts the budget: the live ad sets must follow, not just the profile row.
    with tenant_session(DEMO_TENANT_ID) as s:
        profile = s.scalar(select(BusinessProfile).where(
            BusinessProfile.account_id == DEMO_ACCOUNT_ID))
        profile.daily_budget_paise = 50000
        changed = pipeline.reconcile_budgets(
            s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
        assert changed >= 1
    with tenant_session(DEMO_TENANT_ID) as s:
        total = sum(a.budget_paise for a in s.scalars(select(AdSet).where(
            AdSet.account_id == DEMO_ACCOUNT_ID,
            AdSet.status == CampaignStatus.ACTIVE.value)).all())
        # Proportional rescale (min-clamps may leave slight excess, never > old total).
        assert total <= 60000


def _admin_headers() -> dict:
    out = create_admin("9800022222", "Ops")
    with platform_session() as s:
        from leadpilot.core.models import User

        u = s.get(User, out["user_id"])
        token = issue_access_token(user_id=str(u.id), tenant_id=str(u.tenant_id),
                                   account_id=None, role=u.role,
                                   token_version=u.token_version)
    return {"Authorization": f"Bearer {token}"}


def test_admin_fleet_digest_and_mark_paid(seeded):
    client = TestClient(app)
    h = _admin_headers()

    fleet = client.get("/api/v1/admin/accounts", headers=h)
    assert fleet.status_code == 200
    row = next(r for r in fleet.json() if r["id"] == str(DEMO_ACCOUNT_ID))
    assert "today_spend_paise" in row and "leads_today" in row and "meta_status" in row

    digest = client.get("/api/v1/admin/digest", headers=h)
    assert digest.status_code == 200 and "clients" in digest.json()

    # Manual billing: TRIAL → ACTIVE so trial_sweep never pauses a paying client.
    with platform_session() as s:
        sub = s.scalar(select(Subscription).where(
            Subscription.account_id == DEMO_ACCOUNT_ID))
        if sub is None:
            sub = Subscription(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                               tier="GROWTH", status="TRIAL")
            s.add(sub)
        else:
            sub.status = "TRIAL"
    r = client.post(f"/api/v1/admin/accounts/{DEMO_ACCOUNT_ID}/subscription/mark-paid",
                    headers=h)
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE"


def test_owner_cannot_use_admin_surfaces(seeded):
    client = TestClient(app)
    r = client.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE})
    code = r.json()["dev_code"]
    tk = client.post("/api/v1/auth/otp/verify",
                     json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    h = {"Authorization": f"Bearer {tk['access']}"}
    assert client.get("/api/v1/admin/digest", headers=h).status_code == 403
    assert client.post(
        f"/api/v1/admin/accounts/{DEMO_ACCOUNT_ID}/subscription/mark-paid",
        headers=h).status_code == 403


def test_token_shapes_never_reach_logs():
    assert "[token]" in redact_text("Graph 401: EAAGabc123def456ghi789jkl invalid")
    assert "[token]" in redact_text("header Bearer abcdefghijklmnopqrstuvwxyz012345")
    # Entity ids must survive (UUIDs are how the operator correlates anything).
    uuid_line = "campaign 3f9e1c2a-1b2c-4d5e-8f90-aabbccddeeff paused"
    assert "3f9e1c2a-1b2c-4d5e-8f90-aabbccddeeff" in redact_text(uuid_line)
