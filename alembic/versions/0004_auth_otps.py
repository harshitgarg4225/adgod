"""auth_otps (real OTP storage)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-30
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from leadpilot.common.config import settings
from leadpilot.core.models import Base

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = settings.app_tenant_db_role


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())  # creates auth_otps only
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS auth_otps CASCADE")
