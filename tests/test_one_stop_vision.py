"""The one-stop vision, end to end: the owner sets a GOAL (target cost per lead) and a
budget; Saathi researches, builds ads on Facebook AND Instagram, optimises toward the
goal, and keeps self-learning (monthly research refresh) — verified against the spec the
owner cares about."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from leadpilot.bff.app import app
from leadpilot.core.db import tenant_session
from leadpilot.core.models import AdSet, BusinessBrief, Creative
from leadpilot.saathi import pipeline
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID
from leadpilot.worker.tasks.maintenance import refresh_stale_research


def _auth(client: TestClient) -> tuple[dict, str]:
    r = client.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE})
    code = r.json()["dev_code"]
    tk = client.post("/api/v1/auth/otp/verify",
                     json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    return {"Authorization": f"Bearer {tk['access']}"}, tk["user"]["account_id"]


def _launch():
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
        for c in s.scalars(select(Creative).where(
                Creative.account_id == DEMO_ACCOUNT_ID)).all():
            if c.compliance_status == "PASSED":
                c.approval_status = "APPROVED_FOR_LAUNCH"
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)


# ── the GOAL is the owner's, visible and settable ────────────────────────────

def test_owner_sets_and_sees_the_goal(seeded):
    client = TestClient(app)
    h, account_id = _auth(client)
    # Read: settings exposes the goal.
    s = client.get(f"/api/v1/accounts/{account_id}/settings", headers=h).json()
    assert "target_cpql_paise" in s and "target_cpql_display" in s
    # Write: owner raises what a lead is worth → the optimizer's target follows.
    r = client.patch(f"/api/v1/accounts/{account_id}/settings", headers=h,
                     json={"target_cpql_paise": 40000})
    assert r.status_code == 200 and r.json()["target_cpql_paise"] == 40000
    with tenant_session(DEMO_TENANT_ID) as ses:
        from leadpilot.core.models import Account

        assert ses.get(Account, DEMO_ACCOUNT_ID).target_cpql_paise == 40000


def test_onboarding_accepts_the_goal(seeded):
    client = TestClient(app)
    h, account_id = _auth(client)
    r = client.post("/api/v1/onboarding/business", headers=h, json={
        "business_name": "Verma Dental", "category": "clinic", "offer": "Braces & implants",
        "city": "Indore", "radius_km": 8, "daily_budget_paise": 80000,
        "target_cpql_paise": 30000, "language": "hi"})
    assert r.status_code == 200
    with tenant_session(DEMO_TENANT_ID) as ses:
        from leadpilot.core.models import Account

        assert ses.get(Account, DEMO_ACCOUNT_ID).target_cpql_paise == 30000


# ── Facebook AND Instagram, guaranteed ───────────────────────────────────────

def test_ads_run_on_facebook_and_instagram(seeded):
    _launch()
    with tenant_session(DEMO_TENANT_ID) as s:
        adsets = s.scalars(select(AdSet).where(
            AdSet.account_id == DEMO_ACCOUNT_ID)).all()
        assert adsets
        for a in adsets:
            plats = a.targeting.get("publisher_platforms")
            assert plats == ["facebook", "instagram"]  # never left to default expansion


# ── self-learning never stops ────────────────────────────────────────────────

def test_monthly_research_refresh_versions_brief_without_disturbing_live(seeded):
    _launch()
    with tenant_session(DEMO_TENANT_ID) as s:
        from leadpilot.core.models import Account

        acct = s.get(Account, DEMO_ACCOUNT_ID)
        assert acct.phase in ("LIVE", "OPTIMIZING")
        v_before = s.scalar(select(func.max(BusinessBrief.version)).where(
            BusinessBrief.account_id == DEMO_ACCOUNT_ID))
        # Age the brief past the 30-day staleness gate.
        s.execute(
            BusinessBrief.__table__.update()
            .where(BusinessBrief.account_id == DEMO_ACCOUNT_ID)
            .values(created_at=func.now() - __import__("datetime").timedelta(days=40)))

    out = refresh_stale_research()
    assert out["refreshed"] == 1
    with tenant_session(DEMO_TENANT_ID) as s:
        from leadpilot.core.models import Account

        acct = s.get(Account, DEMO_ACCOUNT_ID)
        # Fresh brief version, but the account never left the live loop.
        v_after = s.scalar(select(func.max(BusinessBrief.version)).where(
            BusinessBrief.account_id == DEMO_ACCOUNT_ID))
        assert v_after > v_before
        assert acct.phase in ("LIVE", "OPTIMIZING")


def test_fresh_account_is_not_refreshed(seeded):
    # A brief created today must NOT trip the staleness gate.
    _launch()
    assert refresh_stale_research()["refreshed"] == 0
