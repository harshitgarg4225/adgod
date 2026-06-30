"""hot-path + retention indexes (data-layer audit P1)

Adds the indexes the audit found missing: webhook status callbacks were seq-scanning the
largest table (messages.wa_message_id), the reaper/backfill scans of unprocessed inbound
events had no index, the DLQ triage filters were unindexed, and the unread-notification
count on the dashboard had no partial index. Also a tighter partial index for the outbox
claim query and a created_at index for idempotency-key retention sweeps.

NOTE: these use plain CREATE INDEX (cheap on the still-small tables here). On a large,
live database run the equivalent CREATE INDEX CONCURRENTLY out of band to avoid write
locks — see docs/ARCHITECTURE.md.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-30
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = [
    ("ix_messages_wa_msg_id",
     "CREATE INDEX IF NOT EXISTS ix_messages_wa_msg_id ON messages (wa_message_id) "
     "WHERE wa_message_id IS NOT NULL"),
    ("ix_inbound_unprocessed",
     "CREATE INDEX IF NOT EXISTS ix_inbound_unprocessed ON inbound_events (created_at) "
     "WHERE processed_at IS NULL"),
    ("ix_dlq_account_created",
     "CREATE INDEX IF NOT EXISTS ix_dlq_account_created ON dlq (account_id, created_at)"),
    ("ix_dlq_source_created",
     "CREATE INDEX IF NOT EXISTS ix_dlq_source_created ON dlq (source, created_at)"),
    ("ix_idem_created",
     "CREATE INDEX IF NOT EXISTS ix_idem_created ON idempotency_keys (created_at)"),
    ("ix_outbox_pending",
     "CREATE INDEX IF NOT EXISTS ix_outbox_pending ON outbox (available_at) "
     "WHERE status = 'PENDING'"),
    ("ix_notifications_account_unread",
     "CREATE INDEX IF NOT EXISTS ix_notifications_account_unread ON notifications "
     "(account_id) WHERE read_at IS NULL"),
]


def upgrade() -> None:
    for _name, ddl in _INDEXES:
        op.execute(ddl)


def downgrade() -> None:
    for name, _ddl in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
