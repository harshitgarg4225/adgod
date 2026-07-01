"""security columns: JWT revocation, DPDP consent, OTP salt, tenant-scoped idempotency

- users.token_version  → bump to revoke all outstanding JWTs (logout / compromise)
- users.consent_at     → DPDP consent timestamp
- auth_otps.salt       → per-code random salt (OTP no longer hashed with a shared pepper)
- idempotency_keys unique (key) → (tenant_id, key) so a key can't collide across tenants

Idempotent + guarded: migration 0001 builds these tables from the live ORM model via
create_all, so on a from-scratch upgrade the new columns/constraint already exist — the
guards make this migration a no-op there and a real change on an already-populated DB.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-01
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS consent_at TIMESTAMPTZ")
    op.execute("ALTER TABLE auth_otps ADD COLUMN IF NOT EXISTS salt VARCHAR(64)")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_idempotency_key') THEN
                ALTER TABLE idempotency_keys DROP CONSTRAINT uq_idempotency_key;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_idempotency_tenant_key'
            ) THEN
                ALTER TABLE idempotency_keys
                    ADD CONSTRAINT uq_idempotency_tenant_key UNIQUE (tenant_id, key);
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS token_version")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS consent_at")
    op.execute("ALTER TABLE auth_otps DROP COLUMN IF EXISTS salt")
    op.execute(
        "ALTER TABLE idempotency_keys DROP CONSTRAINT IF EXISTS uq_idempotency_tenant_key"
    )
