"""ad pipeline + billing tables (briefs, angles, ad_sets, ads, insights, billing)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-30
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from leadpilot.common.config import settings
from leadpilot.core.models import Base

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = settings.app_tenant_db_role

# New tenant-private tables that must be RLS-forced.
NEW_RLS_TABLES = [
    "business_briefs", "angles", "ad_sets", "ads", "audiences", "ad_insights",
    "optimization_decisions", "approvals", "subscriptions", "invoices",
    "wallet_ledger", "bookings",
]


def upgrade() -> None:
    bind = op.get_bind()
    # create_all is checkfirst=True → only creates the new tables.
    Base.metadata.create_all(bind=bind)

    # Ensure the app role can use the new tables.
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
    )

    for table in NEW_RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")  # reproducible from scratch
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )

    # Hot-path indexes.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ad_insights_acct_ref_date "
        "ON ad_insights (account_id, ref_id, date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_creatives_account_angle ON creatives (account_id, angle_id)"
    )


def downgrade() -> None:
    for table in NEW_RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    for table in [
        "bookings", "wa_templates", "wallet_ledger", "invoices", "subscriptions",
        "approvals", "optimization_decisions", "ad_insights", "audiences", "ads",
        "ad_sets", "angles", "business_briefs",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
