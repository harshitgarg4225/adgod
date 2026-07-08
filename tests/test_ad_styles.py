"""Ad-style templates: the owner picks 'what kind of ad' (offer / festival / social-proof /
problem-solution / urgency / question) or lets Saathi decide. The choice is validated,
persisted, localized, changeable, and actually reaches the Maker copywriter."""
from __future__ import annotations

from fastapi.testclient import TestClient

from leadpilot.bff.app import app
from leadpilot.core.db import tenant_session
from leadpilot.core.models import Account
from leadpilot.saathi import pipeline
from leadpilot.saathi.ad_styles import (
    AD_STYLES,
    is_valid_style,
    style_guidance,
    styles_for_locale,
)
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID


def _auth(client: TestClient) -> tuple[dict, str]:
    r = client.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE})
    code = r.json()["dev_code"]
    tk = client.post("/api/v1/auth/otp/verify",
                     json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    return {"Authorization": f"Bearer {tk['access']}"}, tk["user"]["account_id"]


# ── catalog ──────────────────────────────────────────────────────────────────

def test_catalog_is_complete_and_localized():
    for key, s in AD_STYLES.items():
        assert s["emoji"] and s["guidance"]
        for loc in ("en", "hi", "pa"):
            assert s["label"][loc] and s["desc"][loc], f"{key} missing {loc}"


def test_auto_is_first_recommended_and_guidance_empty():
    for loc in ("en", "hi", "pa"):
        opts = styles_for_locale(loc)
        assert opts[0]["key"] == "auto" and opts[0]["recommended"] is True
        # auto + every catalog style is present
        assert len(opts) == len(AD_STYLES) + 1
    # "auto" produces no forced guidance — Maker chooses freely.
    assert style_guidance(None) == "" and style_guidance("auto") == ""
    assert style_guidance("offer")  # a real style carries guidance


def test_validation():
    assert is_valid_style(None) and is_valid_style("offer")
    assert not is_valid_style("nonsense")


# ── API: list, onboarding persist, settings round-trip ───────────────────────

def test_ad_styles_endpoint_localized(seeded):
    client = TestClient(app)
    h, _ = _auth(client)
    body = client.get("/api/v1/onboarding/ad-styles?locale=pa", headers=h).json()
    assert body["selected"] == "auto"
    keys = [s["key"] for s in body["styles"]]
    assert keys[0] == "auto" and "offer" in keys
    offer = next(s for s in body["styles"] if s["key"] == "offer")
    assert offer["label"] == AD_STYLES["offer"]["label"]["pa"]  # Gurmukhi label


def test_onboarding_accepts_and_persists_style(seeded):
    client = TestClient(app)
    h, account_id = _auth(client)
    r = client.post("/api/v1/onboarding/business", headers=h, json={
        "business_name": "Glow Salon", "category": "salon", "offer": "Haircut + facial combo",
        "city": "Ludhiana", "radius_km": 6, "daily_budget_paise": 60000,
        "target_cpql_paise": 20000, "language": "pa", "ad_style": "offer"})
    assert r.status_code == 200
    with tenant_session(DEMO_TENANT_ID) as s:
        assert s.get(Account, DEMO_ACCOUNT_ID).ad_style == "offer"


def test_onboarding_auto_stores_null(seeded):
    client = TestClient(app)
    h, _ = _auth(client)
    r = client.post("/api/v1/onboarding/business", headers=h, json={
        "business_name": "Glow Salon", "category": "salon", "offer": "Haircut combo",
        "city": "Ludhiana", "daily_budget_paise": 60000, "ad_style": "auto"})
    assert r.status_code == 200
    with tenant_session(DEMO_TENANT_ID) as s:
        assert s.get(Account, DEMO_ACCOUNT_ID).ad_style is None


def test_onboarding_rejects_unknown_style(seeded):
    client = TestClient(app)
    h, _ = _auth(client)
    r = client.post("/api/v1/onboarding/business", headers=h, json={
        "business_name": "Glow Salon", "category": "salon", "offer": "Haircut combo",
        "city": "Ludhiana", "daily_budget_paise": 60000, "ad_style": "hypnotise-them"})
    assert r.status_code == 422


def test_settings_exposes_and_updates_style(seeded):
    client = TestClient(app)
    h, account_id = _auth(client)
    out = client.get(f"/api/v1/accounts/{account_id}/settings", headers=h).json()
    assert out["ad_style"] == "auto"  # default
    r = client.patch(f"/api/v1/accounts/{account_id}/settings", headers=h,
                     json={"ad_style": "festival"})
    assert r.status_code == 200 and r.json()["ad_style"] == "festival"
    # switching back to auto clears it
    r = client.patch(f"/api/v1/accounts/{account_id}/settings", headers=h,
                     json={"ad_style": "auto"})
    assert r.json()["ad_style"] == "auto"
    with tenant_session(DEMO_TENANT_ID) as s:
        assert s.get(Account, DEMO_ACCOUNT_ID).ad_style is None


# ── the chosen style actually reaches the copywriter ─────────────────────────

def test_chosen_style_reaches_the_maker(seeded, monkeypatch):
    from leadpilot.saathi.agents.maker import MakerAgent

    with tenant_session(DEMO_TENANT_ID) as s:
        s.get(Account, DEMO_ACCOUNT_ID).ad_style = "urgency"
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)

    seen: list[dict] = []
    orig = MakerAgent.run

    def spy(self, session, *, tenant_id, account_id, context):
        seen.append(context)
        return orig(self, session, tenant_id=tenant_id, account_id=account_id, context=context)

    monkeypatch.setattr(MakerAgent, "run", spy)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)

    assert seen, "Maker was never called"
    guidance = AD_STYLES["urgency"]["guidance"]
    assert all(c.get("ad_style_guidance") == guidance for c in seen)
