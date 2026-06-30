"""The platform role must bypass RLS for legitimate cross-tenant ops, while the tenant
app role must NOT — the basis for webhook/admin/cron correctness under least privilege."""
from __future__ import annotations

from sqlalchemy import func, select, text

from leadpilot.core.db import platform_session
from leadpilot.core.models import Account


def test_platform_role_provisioned_with_bypassrls(seeded):
    with platform_session() as s:
        row = s.execute(
            text("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'leadpilot_platform'")
        ).first()
        assert row is not None and row[0] is True


def test_app_role_is_rls_bound_but_platform_role_bypasses(seeded):
    # The seeded demo account exists in one tenant.
    with platform_session() as s:
        # Tenant app role + no tenant GUC → RLS hides every account.
        s.execute(text("SET LOCAL ROLE leadpilot_app"))
        assert s.scalar(select(func.count(Account.id))) == 0
    with platform_session() as s:
        # Platform role → cross-tenant visibility (what webhooks/admin/cron rely on).
        s.execute(text("SET LOCAL ROLE leadpilot_platform"))
        assert s.scalar(select(func.count(Account.id))) >= 1
