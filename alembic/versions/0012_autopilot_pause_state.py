"""Autopilot-with-veto window + pause provenance (who paused, what to restore)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Guarded like 0007/0008/0010: 0001 builds fresh schemas from current ORM metadata.
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS auto_approve_hours "
               "INTEGER NOT NULL DEFAULT 6")
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS pause_reason VARCHAR(20)")
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS phase_before_pause VARCHAR(30)")


def downgrade() -> None:
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS phase_before_pause")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS pause_reason")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS auto_approve_hours")
