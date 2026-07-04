"""Owner-lens batch: autopilot-with-veto (auto-approve that never overrides a human),
pause/resume that touches Meta + restores state, call-destination ads, fatigue cooldown
+ fallback rotation, ads-summary, SMS alert no-op safety, and truthful status copy."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from leadpilot.bff.app import app
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.models import Account, AdSet, Approval, Campaign, Creative
from leadpilot.integrations.meta.mock import CREATED
from leadpilot.saathi import pipeline
from leadpilot.saathi.pipeline import _ctwa_cta, _rotated_recently, is_platform_blind
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_OWNER_PHONE, DEMO_TENANT_ID
from leadpilot.worker.tasks.alerts import lead_sms
from leadpilot.worker.tasks.maintenance import auto_approve_pending


def _auth(client: TestClient) -> tuple[dict, str]:
    r = client.post("/api/v1/auth/otp/request", json={"phone": DEMO_OWNER_PHONE})
    code = r.json()["dev_code"]
    tk = client.post("/api/v1/auth/otp/verify",
                     json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    return {"Authorization": f"Bearer {tk['access']}"}, tk["user"]["account_id"]


def _to_pending_approval():
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_research(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.run_creative(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)


def _backdate_approval(hours: int = 7):
    with platform_session() as s:
        s.execute(text(
            "UPDATE approvals SET created_at = :ts WHERE account_id = :a AND status = 'PENDING'"),
            {"ts": datetime.now(UTC) - timedelta(hours=hours), "a": str(DEMO_ACCOUNT_ID)})


# ── autopilot-with-veto ───────────────────────────────────────────────────────

def test_auto_approve_launches_after_window_but_preserves_owner_vetoes(seeded):
    _to_pending_approval()
    # Owner vetoed one creative but never tapped Launch — the classic half-review.
    with tenant_session(DEMO_TENANT_ID) as s:
        creatives = s.scalars(select(Creative).where(
            Creative.account_id == DEMO_ACCOUNT_ID)).all()
        vetoed = creatives[0]
        vetoed.approval_status = "REJECTED"
        vetoed_id = vetoed.id

    # Not yet due → nothing happens.
    assert auto_approve_pending()["approved"] == 0
    _backdate_approval(hours=7)  # default window is 6h
    out = auto_approve_pending()
    assert out["approved"] == 1

    with tenant_session(DEMO_TENANT_ID) as s:
        account = s.get(Account, DEMO_ACCOUNT_ID)
        assert account.phase == "APPROVED"  # launch cron takes it from here
        # The veto MUST survive the autopilot.
        assert s.get(Creative, vetoed_id).approval_status == "REJECTED"
        promoted = s.scalars(select(Creative).where(
            Creative.account_id == DEMO_ACCOUNT_ID,
            Creative.approval_status == "APPROVED_FOR_LAUNCH")).all()
        assert promoted  # the rest went live-ready
        ap = s.scalar(select(Approval).where(Approval.account_id == DEMO_ACCOUNT_ID))
        assert ap.status == "APPROVED" and ap.decided_at is not None


def test_auto_approve_respects_manual_mode_and_zero_hours(seeded):
    _to_pending_approval()
    _backdate_approval()
    with platform_session() as s:
        s.execute(text("UPDATE accounts SET autopilot_level='MANUAL' WHERE id=:a"),
                  {"a": str(DEMO_ACCOUNT_ID)})
    assert auto_approve_pending()["approved"] == 0
    with platform_session() as s:
        s.execute(text(
            "UPDATE accounts SET autopilot_level='ASSISTED', auto_approve_hours=0 "
            "WHERE id=:a"), {"a": str(DEMO_ACCOUNT_ID)})
    assert auto_approve_pending()["approved"] == 0  # 0 = wait for the owner forever


def test_auto_approve_regenerates_when_owner_rejected_everything(seeded):
    _to_pending_approval()
    with tenant_session(DEMO_TENANT_ID) as s:
        for c in s.scalars(select(Creative).where(
                Creative.account_id == DEMO_ACCOUNT_ID)).all():
            c.approval_status = "REJECTED"
        n_before = len(s.scalars(select(Creative).where(
            Creative.account_id == DEMO_ACCOUNT_ID)).all())
    _backdate_approval()
    out = auto_approve_pending()
    assert out["regenerated"] == 1
    with tenant_session(DEMO_TENANT_ID) as s:
        n_after = len(s.scalars(select(Creative).where(
            Creative.account_id == DEMO_ACCOUNT_ID)).all())
        assert n_after > n_before  # a fresh batch exists instead of a silent wedge


# ── pause / resume that actually pauses ─────────────────────────────────────

def _launch_demo():
    _to_pending_approval()
    with tenant_session(DEMO_TENANT_ID) as s:
        for c in s.scalars(select(Creative).where(
                Creative.account_id == DEMO_ACCOUNT_ID)).all():
            if c.compliance_status == "PASSED":
                c.approval_status = "APPROVED_FOR_LAUNCH"
    with tenant_session(DEMO_TENANT_ID) as s:
        pipeline.launch_campaigns(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)


def test_pause_touches_meta_and_resume_restores(seeded):
    _launch_demo()
    client = TestClient(app)
    h, account_id = _auth(client)

    r = client.post(f"/api/v1/accounts/{account_id}/pause", headers=h)
    assert r.json()["paused"] is True
    with tenant_session(DEMO_TENANT_ID) as s:
        account = s.get(Account, DEMO_ACCOUNT_ID)
        assert account.pause_reason == "owner"
        assert account.phase_before_pause in ("LIVE", "OPTIMIZING")
        camp = s.scalar(select(Campaign).where(Campaign.account_id == DEMO_ACCOUNT_ID))
        meta_campaign_id = camp.meta_campaign_id
        assert camp.status == "PAUSED"
    # THE point: Meta itself was told to stop delivering.
    assert CREATED[meta_campaign_id]["status"] == "PAUSED"

    r = client.post(f"/api/v1/accounts/{account_id}/resume", headers=h)
    assert r.json()["paused"] is False
    with tenant_session(DEMO_TENANT_ID) as s:
        account = s.get(Account, DEMO_ACCOUNT_ID)
        assert account.phase in ("LIVE", "OPTIMIZING")
        assert account.pause_reason is None
        camp = s.scalar(select(Campaign).where(Campaign.account_id == DEMO_ACCOUNT_ID))
        assert camp.status == "ACTIVE"
        # Every paused ad set came back — the recovery path.
        assert all(a.status == "ACTIVE" for a in s.scalars(select(AdSet).where(
            AdSet.account_id == DEMO_ACCOUNT_ID)).all())
    assert CREATED[meta_campaign_id]["status"] == "ACTIVE"


def test_prelaunch_pause_is_rejected_not_wedged(seeded):
    with platform_session() as s:
        s.execute(text("UPDATE accounts SET phase='PENDING_APPROVAL' WHERE id=:a"),
                  {"a": str(DEMO_ACCOUNT_ID)})
    client = TestClient(app)
    h, account_id = _auth(client)
    r = client.post(f"/api/v1/accounts/{account_id}/pause", headers=h)
    assert r.status_code == 422  # nothing live to pause — never wedge the pipeline


# ── call-destination ads ─────────────────────────────────────────────────────

def test_call_destination_cta_and_blindness():
    wa = SimpleNamespace(display_phone="+91 98123 45678", mode="CALL")
    cta = _ctwa_cta(wa, "PAGE1")
    assert cta["link"] == "tel:+919812345678"
    assert cta["call_to_action"]["type"] == "CALL_NOW"
    assert is_platform_blind("CALL") and is_platform_blind("APP_DESTINATION")
    assert not is_platform_blind("CLOUD_API")


def test_connect_endpoint_accepts_call_mode(seeded):
    client = TestClient(app)
    h, _ = _auth(client)
    r = client.post("/api/v1/onboarding/whatsapp/connect", headers=h,
                    json={"mode": "CALL", "phone": "+919812345678"})
    assert r.status_code == 200
    bad = client.post("/api/v1/onboarding/whatsapp/connect", headers=h,
                      json={"mode": "CALL"})
    assert bad.status_code in (400, 422)  # phone is required for CALL


# ── fatigue: cooldown + fallback target ──────────────────────────────────────

def test_fatigue_cooldown_marker(seeded):
    _launch_demo()
    with tenant_session(DEMO_TENANT_ID) as s:
        assert not _rotated_recently(s, DEMO_ACCOUNT_ID)
        from leadpilot.core.models import OptimizationDecision

        s.add(OptimizationDecision(
            tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID, run_id=None,
            level="ADSET", ref_id=DEMO_ACCOUNT_ID, action="REQUEST_CREATIVE",
            reason_code="fatigue_frequency", before={}, after={}, applied=True))
        s.flush()
        assert _rotated_recently(s, DEMO_ACCOUNT_ID)


def test_rotation_falls_back_to_fatigued_adset_without_testing_tier(seeded):
    _launch_demo()
    with tenant_session(DEMO_TENANT_ID) as s:
        # Simulate the default small-budget client: no TESTING tier survives.
        target = None
        for adset in s.scalars(select(AdSet).where(
                AdSet.account_id == DEMO_ACCOUNT_ID)).all():
            if adset.role == "TESTING":
                adset.status = "PAUSED"
            elif target is None:
                target = adset
        created = pipeline.rotate_fresh_creative(
            s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID, target_adset=target)
        assert created is not None  # refresh still works — not structurally dead


# ── surfaces ─────────────────────────────────────────────────────────────────

def test_ads_summary_shows_running_ads(seeded):
    _launch_demo()
    client = TestClient(app)
    h, account_id = _auth(client)
    body = client.get(f"/api/v1/accounts/{account_id}/ads-summary", headers=h).json()
    assert body["campaign"]["status"] == "ACTIVE"
    assert body["campaign"]["destination"] in ("whatsapp", "call")
    assert body["creatives"] and all(
        c["review"] in ("active", "in_review", "rejected") for c in body["creatives"])


def test_saathi_status_is_truthful_pre_launch(seeded):
    _to_pending_approval()  # ASSISTED default → veto window active
    client = TestClient(app)
    h, account_id = _auth(client)
    home = client.get(f"/api/v1/accounts/{account_id}/home", headers=h).json()
    line = home["saathi_status"]
    assert "24×7" not in line and "watching" not in line.lower()  # nothing is live yet
    assert home["campaign_status"] != ["Pending Approval"]  # no raw enum jargon


def test_lead_sms_is_safe_noop_in_mock_mode(seeded):
    # Never raises, never sends without a DLT flow id — alerting can't break intake.
    assert lead_sms(str(DEMO_TENANT_ID), str(DEMO_ACCOUNT_ID), str(DEMO_ACCOUNT_ID)) is False
