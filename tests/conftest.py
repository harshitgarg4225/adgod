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
    # Advisory lock: two suites TRUNCATE-ing one database corrupt each other mid-test
    # (observed live as deadlocks + phantom FK failures). The second runner blocks here
    # until the first finishes instead.
    lock_conn = engine.connect()
    lock_conn.execute(text("SELECT pg_advisory_lock(74_2001)"))
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield
    lock_conn.execute(text("SELECT pg_advisory_unlock(74_2001)"))
    lock_conn.close()


@pytest.fixture(autouse=True)
def _clean_db():
    # The mock Meta adapter tracks created objects by name (launch resume support) —
    # clear it so campaigns from one test can't be "found" by the next.
    from leadpilot.integrations.meta.mock import CREATED

    CREATED.clear()
    with engine.begin() as conn:
        tables = conn.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename <> 'alembic_version'"
            )
        ).scalars().all()
        if tables:
            conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    # Clear rate-limit counters so OTP-using tests don't accumulate across the run.
    try:
        import redis

        from leadpilot.common.config import settings

        r = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        keys = list(r.scan_iter("rl:*"))
        if keys:
            r.delete(*keys)
    except Exception:
        pass
    yield


@pytest.fixture
def seeded():
    from leadpilot.scripts.seed_demo import seed

    seed()
