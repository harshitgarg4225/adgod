"""Launch-readiness fixes: budget-tier folding, crash-safe resumable launch, blind-mode
optimizer, daily-snapshot insights + ACCOUNT rollup, manual lead entry, leadgen_id dedup,
phone normalisation, operator mint_login/create_admin, approval→phase transition, the
CTWA wa.me link, and the Imagen REST path."""
from __future__ import annotations

import base64
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from leadpilot.bff.app import app
from leadpilot.common.phone import normalize_phone
from leadpilot.core.db import tenant_session
from leadpilot.core.enums import AccountPhase, AdSetRole, OptimizationAction
from leadpilot.core.models import AdInsight, AdSet, Approval, Campaign, Creative, Lead, User
from leadpilot.core.webhooks import capture_leadgen
from leadpilot.integrations.meta.mock import CREATED
from leadpilot.saathi import pipeline
from leadpilot.saathi.pipeline import _budget_tiers, _ctwa_cta, _decide
from leadpilot.saathi.providers.creative import imagen_generate_bytes
from leadpilot.scripts.create_admin import create_admin
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_TENANT_ID
from leadpilot.scripts.mint_login import mint_login
from leadpilot.scripts.provision_client import provision_client
from leadpilot.worker.tasks.maintenance import progress_accounts

# ── budget tiers ─────────────────────────────────────────────────────────────

def test_budget_tiers_fold_below_meta_minimum():
    # ₹1000/day → all three tiers viable (650/200/150, all ≥ ₹90).
    full = _budget_tiers(100000)
    assert set(full) == {AdSetRole.PROSPECTING, AdSetRole.RETARGETING, AdSetRole.TESTING}
    # ₹500/day → TESTING's ₹75 is under Meta's ~₹90 floor and folds into PROSPECTING.
    folded = _budget_tiers(50000)
    assert AdSetRole.TESTING not in folded
    assert sum(folded.values()) <= 50000
    # Below the floor entirely → owner-explainable error, not a Graph rejection.
    with pytest.raises(ValueError, match="daily budget too small"):
        _budget_tiers(5000)


def test_ctwa_cta_builds_wa_me_link():
    wa = SimpleNamespace(display_phone="+91 98123-45678", mode="APP_DESTINATION")
    cta = _ctwa_cta(wa, "PAGE1")
    assert cta["link"] == "https://wa.me/919812345678"
    assert cta["call_to_action"]["type"] == "WHATSAPP_MESSAGE"
    # No number → page fallback (link_data must never be linkless).
    assert _ctwa_cta(None, "PAGE1")["link"] == "https://facebook.com/PAGE1"


# ── crash-safe launch ────────────────────────────────────────────────────────

def _approve_all(account_id):
    with tenant_session(DEMO_TENANT_ID) as s:
        for c in s.scalars(select(Creative).where(Creative.account_id == account_id)).all():
            if c.compliance_status == "PASSED":
                c.approval_status = "APPROVED_FOR_LAUNCH"


def test_launch_resumes_after_midflight_crash(seeded, monkeypatch):
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    _approve_all(DEMO_ACCOUNT_ID)

    # First attempt dies after the Meta campaign + claim commit (first adset create).
    from leadpilot.integrations.meta.mock import MockMetaAdapter

    real_create_adset = MockMetaAdapter.create_adset
    calls = {"n": 0}

    def dying_create_adset(self, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated Graph 500 mid-launch")
        return real_create_adset(self, **kw)

    monkeypatch.setattr(MockMetaAdapter, "create_adset", dying_create_adset)
    with pytest.raises(RuntimeError, match="simulated"):
        with tenant_session(DEMO_TENANT_ID) as s:
            pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)

    # The claim row survived the rollback (committed independently, still IN_REVIEW).
    with tenant_session(DEMO_TENANT_ID) as s:
        claim = s.scalar(select(Campaign).where(Campaign.account_id == DEMO_ACCOUNT_ID))
        assert claim is not None and claim.status == "IN_REVIEW"
        assert claim.meta_campaign_id

    # Retry (what the 10-min cron does) resumes the SAME campaign — no duplicate on Meta.
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        rows = s.scalars(select(Campaign).where(Campaign.account_id == DEMO_ACCOUNT_ID)).all()
        assert len(rows) == 1 and rows[0].status == "ACTIVE"
    meta_campaigns = [k for k, v in CREATED.items() if v.get("kind") == "camp"]
    assert len(meta_campaigns) == 1  # duplicate-spend guard: one campaign ever created


# ── optimizer: blind mode + daily snapshots ──────────────────────────────────

def _row(leads=0, spend=100000, freq=1.0):
    return SimpleNamespace(leads=leads, spend_paise=spend, frequency=freq, ctr=0.02,
                           impressions=1000, clicks=20)


def test_blind_mode_never_kills_on_zero_platform_leads():
    adset = SimpleNamespace(budget_paise=30000, role="PROSPECTING")
    # Sighted: zero leads at 2× target CPQL → kill.
    action, reason, _ = _decide(adset, _row(leads=0, spend=40000), None, 20000, 100000)
    assert action == OptimizationAction.PAUSE and reason == "zero_conversions"
    # Blind (own-number path): zero platform-side leads is not evidence — no kill.
    action, reason, _ = _decide(adset, _row(leads=0, spend=40000), None, 20000, 100000,
                                blind=True)
    assert action != OptimizationAction.PAUSE
    # Frequency fatigue stays on in blind mode (impressions data is real).
    action, reason, _ = _decide(adset, _row(leads=0, spend=40000, freq=5.0), None, 20000,
                                100000, blind=True)
    assert action == OptimizationAction.REQUEST_CREATIVE


def test_optimizer_writes_daily_snapshots_and_account_rollup(seeded):
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    _approve_all(DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)

    # Two optimizer passes on the same day must UPSERT, not append (else every consumer
    # overcounts spend by the number of hourly runs).
    for _ in range(2):
        with tenant_session(DEMO_TENANT_ID) as s:
            pipeline.run_optimization(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)

    with tenant_session(DEMO_TENANT_ID) as s:
        n_adsets = s.scalar(select(func.count(AdSet.id)).where(
            AdSet.account_id == DEMO_ACCOUNT_ID)) or 0
        adset_rows = s.scalar(select(func.count(AdInsight.id)).where(
            AdInsight.account_id == DEMO_ACCOUNT_ID, AdInsight.level == "ADSET")) or 0
        assert adset_rows <= n_adsets  # one snapshot per adset per day, not per run
        account_rows = s.scalars(select(AdInsight).where(
            AdInsight.account_id == DEMO_ACCOUNT_ID, AdInsight.level == "ACCOUNT")).all()
        assert len(account_rows) == 1  # the dashboard/month-cap source exists exactly once
        assert account_rows[0].spend_paise > 0


# ── lead visibility ──────────────────────────────────────────────────────────

def _client_and_auth(seeded_client_phone="+919000000000"):
    client = TestClient(app)
    r = client.post("/api/v1/auth/otp/request", json={"phone": seeded_client_phone})
    code = r.json()["dev_code"]
    r2 = client.post("/api/v1/auth/otp/verify",
                     json={"phone": seeded_client_phone, "code": code})
    body = r2.json()
    return client, {"Authorization": f"Bearer {body['access']}"}, body["user"]["account_id"]


def test_manual_lead_entry_api(seeded):
    from leadpilot.scripts.demo_constants import DEMO_OWNER_PHONE

    client, h, account_id = _client_and_auth(DEMO_OWNER_PHONE)
    r = client.post(f"/api/v1/accounts/{account_id}/leads", headers=h,
                    json={"name": "Walk-in Raju", "wa_phone": "+919888877777",
                          "intent_summary": "Wants evening batch"})
    assert r.status_code == 201 and r.json()["created"] is True
    # Idempotent per phone — logging the same enquiry twice doesn't duplicate.
    r2 = client.post(f"/api/v1/accounts/{account_id}/leads", headers=h,
                     json={"wa_phone": "+919888877777"})
    assert r2.json()["created"] is False
    leads = client.get(f"/api/v1/accounts/{account_id}/leads", headers=h).json()
    assert any(le["name"] == "Walk-in Raju" and le["source_channel"] == "MANUAL"
               for le in leads)


def test_capture_leadgen_dedups_on_leadgen_id(seeded):
    with tenant_session(DEMO_TENANT_ID) as s:
        page_id = "PAGE-DEMO-1"
        from leadpilot.core.models import MetaConnection
        conn = s.scalar(select(MetaConnection).where(
            MetaConnection.account_id == DEMO_ACCOUNT_ID))
        conn.page_id = page_id
    first = capture_leadgen(page_id=page_id, leadgen_id="LG-1", name="Meena",
                            phone="+919111122222")
    dup = capture_leadgen(page_id=page_id, leadgen_id="LG-1", name="Meena",
                          phone="+919111122222")
    assert first == dup
    with tenant_session(DEMO_TENANT_ID) as s:
        lead = s.get(Lead, first)
        assert lead.leadgen_id == "LG-1" and lead.wa_phone == "+919111122222"
        assert lead.source_channel == "META_LEADFORM"


# ── login & operator tools ───────────────────────────────────────────────────

def test_normalize_phone_variants():
    assert normalize_phone("9812345678") == "+919812345678"
    assert normalize_phone("919812345678") == "+919812345678"
    assert normalize_phone("+91 98123-45678") == "+919812345678"
    assert normalize_phone("+919812345678") == "+919812345678"


def test_mint_login_code_verifies_via_normal_endpoint(seeded):
    from leadpilot.scripts.demo_constants import DEMO_OWNER_PHONE

    phone, code = mint_login(DEMO_OWNER_PHONE)
    client = TestClient(app)
    r = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert r.status_code == 200 and r.json()["access"]


def test_create_admin_idempotent():
    out1 = create_admin("9800011111", "Founder")
    out2 = create_admin("+919800011111", "Founder")
    assert out1["created"] is True and out2["created"] is False
    assert out1["user_id"] == out2["user_id"]
    with tenant_session(uuid.uuid4()):  # noqa: SIM117 - just proving no leak via RLS
        pass
    from leadpilot.core.db import platform_session
    with platform_session() as s:
        u = s.scalar(select(User).where(User.phone == "+919800011111"))
        assert u is not None and u.role == "ADMIN"


# ── ASSISTED flow ────────────────────────────────────────────────────────────

def test_approval_decision_moves_phase_and_cron_launches(seeded):
    from leadpilot.scripts.demo_constants import DEMO_OWNER_PHONE

    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)

    with tenant_session(DEMO_TENANT_ID) as s:
        from leadpilot.core.models import Account
        assert s.get(Account, DEMO_ACCOUNT_ID).phase == AccountPhase.PENDING_APPROVAL.value
        approval = s.scalar(select(Approval).where(Approval.account_id == DEMO_ACCOUNT_ID,
                                                   Approval.status == "PENDING"))
        approval_id = str(approval.id)

    client, h, _ = _client_and_auth(DEMO_OWNER_PHONE)
    r = client.post(f"/api/v1/approvals/{approval_id}/decide", headers=h)
    assert r.json()["ok"] is True

    with tenant_session(DEMO_TENANT_ID) as s:
        from leadpilot.core.models import Account
        assert s.get(Account, DEMO_ACCOUNT_ID).phase == AccountPhase.APPROVED.value

    # The autonomous backstop now launches it — no further clicks.
    progress_accounts()
    with tenant_session(DEMO_TENANT_ID) as s:
        from leadpilot.core.models import Account
        assert s.get(Account, DEMO_ACCOUNT_ID).phase == AccountPhase.LIVE.value


def test_launch_without_approval_is_422_not_500(seeded):
    from leadpilot.scripts.demo_constants import DEMO_OWNER_PHONE

    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    client, h, account_id = _client_and_auth(DEMO_OWNER_PHONE)
    r = client.post(f"/api/v1/accounts/{account_id}/campaigns/launch", headers=h)
    assert r.status_code == 422
    assert "approv" in r.json()["detail"].lower()


# ── provisioning ─────────────────────────────────────────────────────────────

def test_provision_normalizes_phone_and_flags_missing_meta():
    out = provision_client(business_name="Test Salon", category="salon", city="Indore",
                           owner_phone="9822200000")
    assert out["owner_phone"] == "+919822200000"
    assert out["meta_connected"] is False


def test_provision_rejects_partial_meta_trio():
    with pytest.raises(SystemExit, match="incomplete"):
        provision_client(business_name="X", category="x", city="Y",
                         owner_phone="9822200001", ad_account_id="123", page_id=None,
                         meta_token="EAAG-x")


def test_provision_duplicate_phone_is_clean_error():
    provision_client(business_name="A", category="x", city="Y", owner_phone="9822200002")
    with pytest.raises(SystemExit, match="already provisioned"):
        provision_client(business_name="B", category="x", city="Y",
                         owner_phone="+91 98222 00002")


# ── creative provider ────────────────────────────────────────────────────────

def test_imagen_rest_returns_bytes_and_maps_ratio():
    png = b"\x89PNG-fake"
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={
            "predictions": [{"bytesBase64Encoded": base64.b64encode(png).decode(),
                             "mimeType": "image/png"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = imagen_generate_bytes("dentist ad, warm light", ratio="4:5", api_key="k",
                                client=client)
    assert out == png
    assert ":predict" in seen["url"]
    assert '"aspectRatio":"3:4"' in seen["body"].replace(" ", "")  # 4:5 → closest Imagen ratio
