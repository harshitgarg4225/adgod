"""Ad-style template choice per account (owner picks 'what kind of ad'; NULL = Saathi decides)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-08
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Guarded like 0010/0012: 0001 builds fresh schemas from current ORM metadata, so a
    # from-scratch DB already has this column — only an in-place upgrade needs to add it.
    op.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS ad_style VARCHAR(30)")


def downgrade() -> None:
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS ad_style")
