"""audit_logs + feature_flags (admin/ops back-office)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-30
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from leadpilot.common.config import settings
from leadpilot.core.models import Base

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = settings.app_tenant_db_role


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())  # creates only the new tables
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_created ON audit_logs (created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS feature_flags CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
