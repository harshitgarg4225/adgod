"""Database engine + tenant-scoped sessions enforcing Row-Level Security.

Multi-tenancy contract:
  * Every tenant-private table has RLS FORCED with a policy
    `USING (tenant_id = current_setting('app.tenant_id', true)::uuid)`.
  * `tenant_session(tenant_id)` opens a transaction, switches to the non-superuser
    app role (`SET LOCAL ROLE`), and sets `app.tenant_id`. A forgotten WHERE clause
    then physically cannot read another tenant's rows. Switching to the app role
    also makes RLS apply in CI where the base connection is a superuser (superusers
    otherwise bypass RLS even when it is FORCED).
  * `SET LOCAL` is transaction-scoped, so both the role and the GUC reset on
    commit/rollback — safe with connection pooling.
  * `platform_session()` runs as the base role with no tenant GUC — used ONLY for
    the routing tables (wa_routes) and global config, which are not RLS-bound.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from leadpilot.common.config import settings

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

engine = create_engine(
    settings.db_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    future=True,
)


def dispose_engine() -> None:
    """Drop pooled connections — call from Celery's worker_process_init so each prefork
    child starts with its own fresh pool (never share a connection across fork)."""
    engine.dispose()

SessionFactory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def _validated_role(role: str | None) -> str | None:
    if not role:
        return None
    if not _IDENT_RE.match(role):
        raise ValueError(f"Unsafe DB role identifier: {role!r}")
    return role


def _app_role() -> str | None:
    return _validated_role(settings.app_tenant_db_role)


def _platform_role() -> str | None:
    return _validated_role(settings.app_platform_db_role)


@contextmanager
def tenant_session(tenant_id: UUID | str) -> Iterator[Session]:
    """A transaction scoped to one tenant via app role + `app.tenant_id` GUC."""
    session = SessionFactory()
    try:
        role = _app_role()
        if role:
            session.execute(text(f"SET LOCAL ROLE {role}"))
        elif settings.is_production:
            # Fail-closed: without the non-superuser app role, RLS would not apply and one
            # tenant could read another's rows. Never run a tenant query unprotected in prod.
            raise RuntimeError(
                "APP_TENANT_DB_ROLE must be set in production (RLS depends on it)"
            )
        session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def platform_session() -> Iterator[Session]:
    """A transaction for legitimate cross-tenant work (routing, webhooks, admin, cron).

    Switches to the BYPASSRLS platform role when configured, so it works even when the
    app's base connection is the least-privilege tenant role. With no platform role set,
    it runs as the base role (correct only if that role can bypass RLS — local/CI).
    """
    session = SessionFactory()
    try:
        role = _platform_role()
        if role:
            session.execute(text(f"SET LOCAL ROLE {role}"))
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def healthcheck() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
