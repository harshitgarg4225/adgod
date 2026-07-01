"""Go-live hardening: DB-URL normalisation, tenant-role fail-closed, Meta leadgen GET
handshake, real-client-IP behind a proxy, and the prod secret guard workers now run."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from leadpilot.common.config import Settings, settings
from leadpilot.common.requtil import client_ip
from leadpilot.core.db import tenant_session
from leadpilot.webhook.app import app


def test_db_url_normalised_to_psycopg():
    assert Settings._with_psycopg("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert Settings._with_psycopg("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    # Already-explicit drivers are left untouched.
    assert Settings._with_psycopg("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
    assert Settings._with_psycopg("postgresql+asyncpg://u@h/db") == "postgresql+asyncpg://u@h/db"


def test_tenant_session_fails_closed_without_role_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "app_tenant_db_role", "")  # RLS would not apply
    with pytest.raises(RuntimeError, match="APP_TENANT_DB_ROLE"):
        with tenant_session(uuid4()):
            pass


def test_meta_leadgen_get_handshake():
    c = TestClient(app)
    token = settings.meta_webhook_verify_token or settings.whatsapp_webhook_verify_token
    r = c.get("/webhooks/meta/leadgen", params={
        "hub.mode": "subscribe", "hub.verify_token": token, "hub.challenge": "xyz123"})
    assert r.status_code == 200 and r.text == "xyz123"
    bad = c.get("/webhooks/meta/leadgen", params={
        "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "x"})
    assert bad.status_code == 403


def _req(xff: str | None, host: str = "10.0.0.1"):
    headers = {"x-forwarded-for": xff} if xff else {}
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


def test_client_ip_uses_forwarded_for_when_trusting_proxy(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy", True)
    assert client_ip(_req("1.2.3.4, 5.6.7.8")) == "1.2.3.4"     # real client, not proxy
    assert client_ip(_req(None, host="9.9.9.9")) == "9.9.9.9"    # no XFF → socket peer


def test_client_ip_ignores_forwarded_for_without_trust(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy", False)
    assert client_ip(_req("1.2.3.4", host="10.0.0.1")) == "10.0.0.1"


def test_prod_secret_guard_raises(monkeypatch):
    # The check workers now run at boot: production + dev-default secrets must refuse.
    import leadpilot.common.observability as obs

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "jwt_secret", "dev-only-change-me")
    monkeypatch.setattr(obs, "_inited", False)
    with pytest.raises(SystemExit):
        obs.init_observability("celery-worker")
