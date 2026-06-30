"""Unit coverage for the security-hardening fixes: IDOR-safe account access, CSV
formula-injection neutralisation, fail-closed webhook posture, and fail-closed rate
limiting on a Redis outage."""
from __future__ import annotations

import pytest

from leadpilot.bff.deps import Principal, require_account_access
from leadpilot.bff.routers.leads import _csv_safe
from leadpilot.common.errors import ForbiddenError


def _p(role: str, account_id: str | None) -> Principal:
    return Principal(user_id="u", tenant_id="t", account_id=account_id, role=role)


def test_owner_with_no_account_is_denied_not_allowed_everything():
    # The IDOR fix: a null account_id must NOT grant access to an arbitrary account.
    with pytest.raises(ForbiddenError):
        require_account_access(_p("OWNER", None), "acc-1")


def test_owner_can_only_touch_own_account():
    require_account_access(_p("OWNER", "acc-1"), "acc-1")  # ok
    with pytest.raises(ForbiddenError):
        require_account_access(_p("OWNER", "acc-1"), "acc-2")


def test_admin_ops_partner_act_tenant_wide():
    for role in ("ADMIN", "OPS", "PARTNER"):
        require_account_access(_p(role, None), "any-account")  # no raise


def test_csv_safe_neutralises_formula_injection():
    assert _csv_safe("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert _csv_safe("+1") == "'+1"
    assert _csv_safe("-2") == "'-2"
    assert _csv_safe("@SUM(A1)") == "'@SUM(A1)"
    assert _csv_safe("Ramesh") == "Ramesh"  # benign text untouched
    assert _csv_safe("") == ""


def test_requires_secure_webhooks_fails_closed_for_unknown_env(monkeypatch):
    from leadpilot.common.config import settings

    for env, secure in [
        ("development", False), ("dev", False), ("test", False), ("local", False),
        ("production", True), ("prod", True), ("staging", True), ("", True),
    ]:
        monkeypatch.setattr(settings, "environment", env)
        assert settings.requires_secure_webhooks is secure


def test_rate_limit_fails_closed_when_redis_unavailable(monkeypatch):
    from leadpilot.common import ratelimit

    monkeypatch.setattr(ratelimit, "_client", lambda: None)
    # fail-open (default): allow when cache is down — never block the lead path.
    assert ratelimit.allow("x", "id", limit=1, window_s=60) is True
    # fail-closed (auth/billing): deny when cache is down — can't be defeated by an outage.
    assert ratelimit.allow("x", "id", limit=1, window_s=60, fail_closed=True) is False
