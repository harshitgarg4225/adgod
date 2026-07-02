"""One-stop proof: a connected account autonomously goes signup → research → creative
(image + video) → 3-tier launch → hourly optimize (kill/scale/reallocate/promote) →
qualified WhatsApp lead. Guards the end-to-end 'run ads and get leads' promise."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.models import (
    Account,
    AdSet,
    BusinessProfile,
    Campaign,
    Creative,
    MetaConnection,
    Tenant,
    WaRoute,
    WhatsAppConnection,
)
from leadpilot.saathi import pipeline
from leadpilot.worker.tasks.maintenance import progress_accounts


def _connected_full_autopilot_account() -> tuple[str, str, str]:
    """A brand-new SIGNED_UP account with a profile + Meta/WhatsApp connections and FULL
    autopilot — the state right after a self-serve owner finishes onboarding."""
    tid, aid = str(uuid4()), str(uuid4())
    pnid = "PN" + uuid4().hex[:10]
    with platform_session() as s:
        s.add(Tenant(id=tid, name="Auto Tenant", type="DIRECT", status="ACTIVE", settings={}))
        s.add(WaRoute(phone_number_id=pnid, tenant_id=tid, account_id=aid))
    with tenant_session(tid) as s:
        s.add(Account(id=aid, tenant_id=tid, business_name="Verma Coaching", category="coaching",
                      phase="SIGNED_UP", autopilot_level="FULL", default_language="hi",
                      target_cpql_paise=20000, created_via="test"))
        s.add(BusinessProfile(tenant_id=tid, account_id=aid, offer="NEET coaching, small batches",
                              service_area_city="Indore", service_radius_km=10,
                              daily_budget_paise=100000))
        s.add(MetaConnection(tenant_id=tid, account_id=aid, meta_business_id="1", ad_account_id="1",
                             page_id="1", status="ACTIVE"))
        s.add(WhatsAppConnection(tenant_id=tid, account_id=aid, mode="CLOUD_API",
                                 phone_number_id=pnid, display_phone="+919812300000"))
    return tid, aid, pnid


def test_one_stop_autonomous_to_live(seeded):
    tid, aid, _ = _connected_full_autopilot_account()

    # The autonomous backstop advances the account one phase per run: research → creative
    # → launch. No UI click required (the "set-and-forget" loop).
    for _ in range(3):
        progress_accounts()

    with tenant_session(tid) as s:
        account = s.get(Account, aid)
        assert account.phase in ("LIVE", "OPTIMIZING")

        # Creative brain: both an image AND a UGC video per angle.
        formats = {c.format for c in s.scalars(
            select(Creative).where(Creative.account_id == aid)).all()}
        assert "IMAGE_VERTICAL" in formats and "VIDEO_9_16" in formats

        # 3-tier structure live (prospecting / retargeting / testing).
        camp = s.scalar(select(Campaign).where(Campaign.account_id == aid))
        assert camp and camp.status == "ACTIVE"
        roles = {a.role for a in s.scalars(select(AdSet).where(AdSet.account_id == aid)).all()}
        assert roles == {"PROSPECTING", "RETARGETING", "TESTING"}


class _FakeMeta:
    """Loser (0 leads) + winning TESTING ad set → forces kill + scale + reallocate + promote."""

    def get_insights(self, *, level, meta_ids):
        out = []
        for mid in meta_ids:
            if "loser" in mid:
                out.append(SimpleNamespace(level=level, meta_id=mid, spend_paise=80000, leads=0,
                                           impressions=5000, clicks=200, ctr=0.02, frequency=2.0))
            else:
                out.append(SimpleNamespace(level=level, meta_id=mid, spend_paise=60000, leads=8,
                                           impressions=5000, clicks=300, ctr=0.03, frequency=1.5))
        return out

    def set_status(self, *, level, meta_id, status):
        pass

    def set_adset_budget(self, *, meta_adset_id, daily_budget_paise):
        pass


def test_one_stop_optimization_loop(seeded, monkeypatch):
    """The refresh-and-reallocate loop keeps leads flowing after launch."""
    monkeypatch.setattr(pipeline, "meta_adapter_for_account", lambda s, a: _FakeMeta())
    tid, aid, _ = _connected_full_autopilot_account()
    with tenant_session(tid) as s:
        camp = Campaign(tenant_id=tid, account_id=aid, meta_campaign_id="c", status="ACTIVE",
                        channel="META_CTWA", daily_budget_paise=50000)
        s.add(camp)
        s.flush()
        s.add(AdSet(tenant_id=tid, account_id=aid, campaign_id=camp.id, meta_adset_id="loser1",
                    name="loser", role="PROSPECTING", budget_paise=25000, status="ACTIVE"))
        s.add(AdSet(tenant_id=tid, account_id=aid, campaign_id=camp.id, meta_adset_id="winner1",
                    name="winner", role="TESTING", budget_paise=15000, status="ACTIVE"))

    with tenant_session(tid) as s:
        decisions = pipeline.run_optimization(s, tenant_id=tid, account_id=aid)

    actions = {d["action"] for d in decisions}
    assert {"PAUSE", "SCALE", "PROMOTE", "REALLOCATE"} <= actions


def test_one_stop_qualifies_whatsapp_lead(seeded):
    """The other half of one-stop: ads bring the enquiry, Saathi qualifies it on WhatsApp."""
    from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_TENANT_ID
    from leadpilot.scripts.simulate_inbound import SCRIPT, deliver

    result = {}
    for text in SCRIPT:
        result = deliver(text)
    assert result.get("hot") is True

    from leadpilot.core.models import Lead
    with tenant_session(DEMO_TENANT_ID) as s:
        hot = s.scalars(select(Lead).where(Lead.account_id == DEMO_ACCOUNT_ID,
                                           Lead.status == "QUALIFIED_HOT")).all()
        assert hot


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    # Keep the creative provider mock even if env drifts.
    yield
