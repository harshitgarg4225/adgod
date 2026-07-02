"""leads.leadgen_id (Instant-Form dedup key) + one-open-campaign-per-account guard

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-02
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Instant-Form intake (webhook + polling) dedups on the Meta leadgen id instead of
    # abusing wa_phone as a carrier for it.
    op.add_column("leads", sa.Column("leadgen_id", sa.String(60), nullable=True))
    op.create_index("ix_leads_leadgen_id", "leads", ["leadgen_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_leads_account_leadgen ON leads (account_id, leadgen_id) "
        "WHERE leadgen_id IS NOT NULL"
    )
    # Launch races (cron + owner click) must not stack open campaigns: the second claim
    # insert violates this index and the loser resumes the winner's campaign on retry.
    op.execute(
        "CREATE UNIQUE INDEX uq_campaigns_one_open ON campaigns (account_id) "
        "WHERE status IN ('IN_REVIEW', 'ACTIVE')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_campaigns_one_open")
    op.execute("DROP INDEX IF EXISTS uq_leads_account_leadgen")
    op.drop_index("ix_leads_leadgen_id", table_name="leads")
    op.drop_column("leads", "leadgen_id")
