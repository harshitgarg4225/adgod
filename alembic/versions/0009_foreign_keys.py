"""referential integrity: account_id FKs with ON DELETE CASCADE

The ~25 account_id columns were bare UUIDs with no FK, so a delete could orphan rows and
nothing stopped a write referencing a non-existent account. This adds FK constraints with
ON DELETE CASCADE (tenant-owned children clean up when an account is hard-purged).

Added ``NOT VALID`` so the constraint is enforced for new writes immediately WITHOUT
scanning/locking existing rows — safe to run online and tolerant of any pre-existing
orphans. A later maintenance window can ``VALIDATE CONSTRAINT`` if desired.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-01
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables whose account_id should reference accounts(id) and cascade on delete.
_TABLES = [
    "business_profiles", "whatsapp_connections", "meta_connections", "campaigns",
    "leads", "business_briefs", "angles", "creatives", "ad_sets", "ads", "audiences",
    "ad_insights", "optimization_decisions", "approvals", "subscriptions", "invoices",
    "wallet_ledger", "bookings", "notifications", "agent_runs",
]


def upgrade() -> None:
    for table in _TABLES:
        name = f"fk_{table}_account"
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name='{table}' AND column_name='account_id')
                   AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='{name}') THEN
                    ALTER TABLE {table}
                        ADD CONSTRAINT {name}
                        FOREIGN KEY (account_id) REFERENCES accounts(id)
                        ON DELETE CASCADE NOT VALID;
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_account")
