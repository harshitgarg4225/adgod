"""Test harness: migrate once, truncate between tests. Requires a real Postgres
(pgvector) — RLS and the outbox are not mockable. CI provides it as a service."""
from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from leadpilot.core.db import engine


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_db():
    with engine.begin() as conn:
        tables = conn.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename <> 'alembic_version'"
            )
        ).scalars().all()
        if tables:
            conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def seeded():
    from leadpilot.scripts.seed_demo import seed

    seed()
