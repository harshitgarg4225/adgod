"""Retention + trial-expiry cron tasks: bound table growth and drive trial→paid."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.models import Account, Notification, Subscription
from leadpilot.scripts.demo_constants import DEMO_ACCOUNT_ID, DEMO_TENANT_ID
from leadpilot.worker.tasks.maintenance import retention_sweep, trial_sweep


def test_trial_sweep_expires_and_pauses(seeded):
    # Put the demo account on an already-expired trial while its ads are live.
    with tenant_session(DEMO_TENANT_ID) as s:
        s.add(Subscription(
            tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID, tier="GROWTH",
            status="TRIAL", trial_end=datetime.now(UTC) - timedelta(days=1),
        ))
        s.get(Account, DEMO_ACCOUNT_ID).phase = "LIVE"

    out = trial_sweep()
    assert out["expired"] >= 1

    with tenant_session(DEMO_TENANT_ID) as s:
        sub = s.scalar(select(Subscription).where(Subscription.account_id == DEMO_ACCOUNT_ID))
        assert sub.status == "PAST_DUE"
        assert s.get(Account, DEMO_ACCOUNT_ID).phase == "PAUSED"
        notes = s.scalars(
            select(Notification).where(Notification.account_id == DEMO_ACCOUNT_ID,
                                       Notification.kind == "BILLING")
        ).all()
        assert any("trial" in (n.title or "").lower() for n in notes)


def test_trial_sweep_ignores_active_and_future_trials(seeded):
    with tenant_session(DEMO_TENANT_ID) as s:
        s.add(Subscription(
            tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID, tier="GROWTH",
            status="TRIAL", trial_end=datetime.now(UTC) + timedelta(days=3),  # not yet expired
        ))
    assert trial_sweep()["expired"] == 0


def test_retention_sweep_purges_old_otps(seeded):
    # Insert a stale consumed OTP well past the 1-day window.
    with platform_session() as s:
        s.execute(text(
            "INSERT INTO auth_otps (phone, code_hash, expires_at, created_at) "
            "VALUES ('+910000000000', 'x', now() - interval '2 days', now() - interval '2 days')"
        ))
    out = retention_sweep()
    assert out.get("auth_otps", 0) >= 1
    with platform_session() as s:
        remaining = s.execute(
            text("SELECT count(*) FROM auth_otps WHERE phone='+910000000000'")
        ).scalar()
        assert remaining == 0
