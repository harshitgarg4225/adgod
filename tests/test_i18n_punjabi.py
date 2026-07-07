"""Punjabi (pa) is a first-class UI language alongside English and Hindi: the locale is
accepted everywhere a locale is validated, and every deterministic server string an owner
can see has a real Punjabi translation (no silent English fallback)."""
from __future__ import annotations

from leadpilot.common.i18n import STRINGS, SUPPORTED_LOCALES, normalize_locale, t


def test_punjabi_is_a_supported_locale():
    assert "pa" in SUPPORTED_LOCALES
    assert normalize_locale("pa") == "pa"
    assert normalize_locale("pa-IN") == "pa"  # region-tagged still resolves
    # An unsupported locale still fails closed to English.
    assert normalize_locale("xx") == "en"


def test_every_server_string_has_punjabi():
    # No owner-facing server string may silently fall back to English.
    missing = [key for key, table in STRINGS.items() if "pa" not in table]
    assert not missing, f"server strings missing Punjabi: {missing}"


def test_punjabi_strings_are_distinct_from_english():
    # A copy-paste of the English value would defeat the point — spot-check the most-read
    # strings actually differ from English (they're Gurmukhi).
    for key in ("phase.LIVE", "saathi.watching", "notify.hot_lead.title"):
        assert t(key, "pa") != t(key, "en"), f"{key} Punjabi equals English"


def test_punjabi_interpolation_preserves_placeholders():
    out = t("saathi.qualified_today", "pa", n=5)
    assert "5" in out
    out = t("notify.hot_lead.body", "pa", name="Ravi", intent="yoga")
    assert "Ravi" in out and "yoga" in out


def test_settings_patch_accepts_punjabi(seeded):
    from fastapi.testclient import TestClient

    from leadpilot.bff.app import app
    from leadpilot.scripts.demo_constants import DEMO_OWNER_PHONE

    client = TestClient(app)
    code = client.post("/api/v1/auth/otp/request",
                       json={"phone": DEMO_OWNER_PHONE}).json()["dev_code"]
    tok = client.post("/api/v1/auth/otp/verify",
                      json={"phone": DEMO_OWNER_PHONE, "code": code}).json()
    h = {"Authorization": f"Bearer {tok['access']}"}
    acc = tok["user"]["account_id"]
    r = client.patch(f"/api/v1/accounts/{acc}/settings", headers=h,
                     json={"default_language": "pa"})
    assert r.status_code == 200
    assert r.json()["default_language"] == "pa"
