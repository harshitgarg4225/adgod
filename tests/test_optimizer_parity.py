"""Optimizer engine parity: kill rules (zero-conv / >3x CPL / fatigue), scale winners,
promote test winners to prospecting, and reallocate freed budget to winners."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from leadpilot.core.db import tenant_session
from leadpilot.core.enums import OptimizationAction
from leadpilot.core.models import AdSet, Campaign
from leadpilot.saathi import pipeline
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_TENANT_ID

TARGET = 20000  # ₹200 target CPQL


def _row(spend, leads, frequency=1.5, ctr=0.02):
    return SimpleNamespace(spend_paise=spend, leads=leads, frequency=frequency, ctr=ctr,
                           impressions=1000, clicks=100)


def _adset(budget=30000, role="PROSPECTING"):
    return SimpleNamespace(budget_paise=budget, role=role, meta_adset_id="x")


def test_decide_kills_zero_conversions():
    row = _row(spend=45000, leads=0)  # spent > 2x target, no leads
    action, reason, _ = pipeline._decide(_adset(), row, None, TARGET, 50000)
    assert action == OptimizationAction.PAUSE and reason == "zero_conversions"


def test_decide_kills_runaway_cpl():
    row = _row(spend=70000, leads=1)  # cpl = 70000 > 3x target
    action, reason, _ = pipeline._decide(_adset(), row, 70000, TARGET, 50000)
    assert action == OptimizationAction.PAUSE and reason == "cpl_over_3x_target"


def test_decide_refreshes_on_fatigue():
    row = _row(spend=30000, leads=3, frequency=4.5)  # saturated audience
    action, reason, _ = pipeline._decide(_adset(), row, 10000, TARGET, 50000)
    assert action == OptimizationAction.REQUEST_CREATIVE and reason == "fatigue_frequency"


def test_decide_scales_proven_winner():
    row = _row(spend=60000, leads=6)  # cpl 10000 <= target, 5+ leads
    action, reason, after = pipeline._decide(_adset(budget=30000), row, 10000, TARGET, 50000)
    assert action == OptimizationAction.SCALE and reason == "proven_winner"
    assert after["budget_paise"] <= int(30000 * 1.2)  # +20%/day cap honoured


def test_decide_efficient_scale_below_winner_volume():
    row = _row(spend=20000, leads=2)  # efficient but < 5 leads
    action, reason, _ = pipeline._decide(_adset(), row, 10000, TARGET, 50000)
    assert action == OptimizationAction.SCALE and reason == "efficient_scale"


def test_decide_stable_noop():
    row = _row(spend=5000, leads=0)  # below the zero-conv spend floor
    action, reason, _ = pipeline._decide(_adset(), row, None, TARGET, 50000)
    assert action == OptimizationAction.NO_OP


# ── Integration: reallocation + promotion via a controlled fake adapter ──

class _FakeMeta:
    """Loser ad set (0 leads, high spend) + winning test ad set (many cheap leads)."""

    def __init__(self):
        self.status_calls = []
        self.budget_calls = {}

    def get_insights(self, *, level, meta_ids):
        out = []
        for mid in meta_ids:
            if mid == "loser":
                out.append(SimpleNamespace(level=level, meta_id=mid, spend_paise=80000, leads=0,
                                           impressions=5000, clicks=200, ctr=0.02, frequency=2.0))
            else:  # winner (a TESTING ad set that should get promoted)
                out.append(SimpleNamespace(level=level, meta_id=mid, spend_paise=60000, leads=8,
                                           impressions=5000, clicks=300, ctr=0.03, frequency=1.5))
        return out

    def set_status(self, *, level, meta_id, status):
        self.status_calls.append((meta_id, status))

    def set_adset_budget(self, *, meta_adset_id, daily_budget_paise):
        self.budget_calls[meta_adset_id] = daily_budget_paise


@pytest.fixture
def seeded_client(seeded):
    return seeded


def test_reallocation_and_promotion(seeded, monkeypatch):
    fake = _FakeMeta()
    monkeypatch.setattr(pipeline, "get_meta_adapter", lambda: fake)

    with tenant_session(DEMO_TENANT_ID) as s:
        camp = Campaign(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                        meta_campaign_id="c1", status="ACTIVE", channel="META_CTWA",
                        daily_budget_paise=50000)
        s.add(camp)
        s.flush()
        s.add(AdSet(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID, campaign_id=camp.id,
                    meta_adset_id="loser", name="loser", role="PROSPECTING",
                    budget_paise=25000, status="ACTIVE"))
        s.add(AdSet(tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID, campaign_id=camp.id,
                    meta_adset_id="winner", name="winner", role="TESTING",
                    budget_paise=15000, status="ACTIVE"))

    with tenant_session(DEMO_TENANT_ID) as s:
        decisions = pipeline.run_optimization(s, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID)

    actions = {d["action"] for d in decisions}
    assert "PAUSE" in actions          # loser killed (zero conversions)
    assert "SCALE" in actions          # winner scaled
    assert "PROMOTE" in actions        # test winner graduated to prospecting
    assert "REALLOCATE" in actions     # freed budget moved to the winner

    with tenant_session(DEMO_TENANT_ID) as s:
        winner = s.scalar(select(AdSet).where(AdSet.meta_adset_id == "winner"))
        assert winner.role == "PROSPECTING"       # promoted
        assert winner.budget_paise > 15000        # scaled + reallocated
        loser = s.scalar(select(AdSet).where(AdSet.meta_adset_id == "loser"))
        assert loser.status == "PAUSED"
