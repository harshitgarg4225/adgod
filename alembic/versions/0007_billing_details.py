"""GST/billing details on accounts (GST-compliant B2B invoices)

Adds gstin / legal_name / billing_address to accounts. Nullable, no default → a fast,
non-rewriting ALTER (safe online).

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-01
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS gstin VARCHAR(20)")
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS legal_name VARCHAR(200)")
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS billing_address TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS gstin")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS legal_name")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS billing_address")
