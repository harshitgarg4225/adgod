"""platform role with BYPASSRLS for cross-tenant ops (webhooks/admin/cron)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-30
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLATFORM_ROLE = "leadpilot_platform"


def upgrade() -> None:
    # Creating a BYPASSRLS role requires superuser. If the migration role isn't a
    # superuser, skip gracefully — the role must then be provisioned out of band, and
    # APP_PLATFORM_DB_ROLE left empty until it exists.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF (SELECT rolsuper FROM pg_roles WHERE rolname = CURRENT_USER) THEN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{PLATFORM_ROLE}') THEN
                    CREATE ROLE {PLATFORM_ROLE} NOLOGIN BYPASSRLS;
                END IF;
                GRANT USAGE ON SCHEMA public TO {PLATFORM_ROLE};
                GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {PLATFORM_ROLE};
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {PLATFORM_ROLE};
                ALTER DEFAULT PRIVILEGES IN SCHEMA public
                    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {PLATFORM_ROLE};
                EXECUTE 'GRANT {PLATFORM_ROLE} TO ' || quote_ident(CURRENT_USER);
            ELSE
                RAISE NOTICE 'Skipping {PLATFORM_ROLE} creation: % is not a superuser', CURRENT_USER;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # The role owns GRANTs + default-privilege ACLs, so a bare DROP ROLE errors with
    # DependentObjectsStillExist. Clear owned objects/ACLs first (guarded on existence).
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{PLATFORM_ROLE}') THEN
                EXECUTE 'REASSIGN OWNED BY {PLATFORM_ROLE} TO ' || quote_ident(CURRENT_USER);
                DROP OWNED BY {PLATFORM_ROLE};
                DROP ROLE {PLATFORM_ROLE};
            END IF;
        END
        $$;
        """
    )
