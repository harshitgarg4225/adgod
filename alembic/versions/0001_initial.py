"""initial schema: core tables, pgvector, RLS, app role

Revision ID: 0001
Revises:
Create Date: 2026-06-29
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from leadpilot.common.config import settings
from leadpilot.core.models import RLS_TABLES, Base

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = settings.app_tenant_db_role


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Extensions (pgvector for semantic memory; gen_random_uuid is built-in on PG13+).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Non-superuser app role used for RLS-bound access. Make the migration role a
    #    member so it can `SET ROLE` to it (needed in CI where we connect as superuser).
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT {APP_ROLE} TO CURRENT_USER")

    # 3. All tables from the ORM metadata (keeps DDL in lockstep with models).
    Base.metadata.create_all(bind=bind)

    # 4. Privileges for the app role.
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"
    )
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
    )

    # 5. Row-Level Security: FORCE so even the table owner is bound; isolate by tenant_id.
    #    Idempotent (DROP IF EXISTS) so a from-scratch `upgrade head` is reproducible even
    #    though create_all above may have built tables the model added in later revisions.
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
            """
        )

    # 6. Hot-path indexes (PRD §8.7).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_conv_created "
        "ON messages (conversation_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_leads_account_status_created "
        "ON leads (account_id, status, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_outbox_status_available "
        "ON outbox (status, available_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notifications_account_read "
        "ON notifications (account_id, read_at)"
    )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    Base.metadata.drop_all(bind=op.get_bind())
