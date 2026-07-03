"""RLS on users (tenant-scoped PII) + unique daily-insight key backing the upsert

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-03
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # users carries tenant_id + phone PII but was missing from RLS_TABLES — today every
    # read is platform-role or PK-scoped, but the isolation contract says FORCE RLS on
    # every tenant-private table so a future unscoped query can never cross tenants.
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON users
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """
    )
    # The daily-snapshot upsert (SELECT-then-INSERT) needs a real uniqueness guarantee —
    # concurrent optimizer runs must not double-count spend. Dedup first (keep newest id)
    # in case hourly-append-era rows exist.
    op.execute(
        """
        DELETE FROM ad_insights a USING ad_insights b
        WHERE a.account_id = b.account_id AND a.level = b.level AND a.ref_id = b.ref_id
          AND date_trunc('day', a.date) = date_trunc('day', b.date) AND a.id < b.id
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_ad_insights_daily "
        "ON ad_insights (account_id, level, ref_id, date)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_ad_insights_daily")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
