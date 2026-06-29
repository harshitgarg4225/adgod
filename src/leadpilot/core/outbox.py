"""Transactional outbox — exactly-once *effect* without Temporal.

Pattern:
  1. In the SAME DB transaction that mutates domain state, write an OutboxEntry
     keyed by (account_id, step_id). The unique constraint makes a duplicate
     enqueue a no-op (ON CONFLICT DO NOTHING).
  2. A drainer (WorkflowRunner / Celery) claims PENDING rows with
     FOR UPDATE SKIP LOCKED, performs the external effect through an adapter,
     and marks the row DONE — or FAILED with backoff, eventually DEAD → dlq.
  3. Effect handlers are idempotent (read-modify-write against live provider
     state), so a redelivery never produces a duplicate side effect.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

MAX_ATTEMPTS = 6


def now_utc() -> datetime:
    return datetime.now(UTC)


def enqueue_effect(
    session: Session,
    *,
    tenant_id: UUID | str,
    account_id: UUID | str,
    step_id: str,
    effect_type: str,
    payload: dict,
) -> None:
    """Insert an outbox row idempotently. Call inside the state-mutating txn."""
    session.execute(
        text(
            """
            INSERT INTO outbox (tenant_id, account_id, step_id, effect_type, payload, status)
            VALUES (:tenant_id, :account_id, :step_id, :effect_type, CAST(:payload AS jsonb), 'PENDING')
            ON CONFLICT (account_id, step_id) DO NOTHING
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "account_id": str(account_id),
            "step_id": step_id,
            "effect_type": effect_type,
            "payload": _json(payload),
        },
    )


def claim_pending(session: Session, *, limit: int = 20) -> list[dict]:
    """Claim due PENDING rows (FOR UPDATE SKIP LOCKED) and mark them IN_PROGRESS."""
    rows = session.execute(
        text(
            """
            SELECT id, tenant_id, account_id, step_id, effect_type, payload, attempts
            FROM outbox
            WHERE status = 'PENDING' AND available_at <= now()
            ORDER BY available_at
            FOR UPDATE SKIP LOCKED
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    if rows:
        ids = [r["id"] for r in rows]
        session.execute(
            text("UPDATE outbox SET status='IN_PROGRESS', updated_at=now() WHERE id = ANY(:ids)"),
            {"ids": ids},
        )
    return [dict(r) for r in rows]


def mark_done(session: Session, entry_id: UUID, result: dict | None = None) -> None:
    session.execute(
        text(
            "UPDATE outbox SET status='DONE', result=CAST(:result AS jsonb), updated_at=now() "
            "WHERE id=:id"
        ),
        {"id": str(entry_id), "result": _json(result or {})},
    )


def mark_retry(session: Session, entry_id: UUID, attempts: int, error: str) -> None:
    """Backoff: available_at pushed out exponentially; DEAD after MAX_ATTEMPTS."""
    new_attempts = attempts + 1
    if new_attempts >= MAX_ATTEMPTS:
        session.execute(
            text(
                "UPDATE outbox SET status='DEAD', attempts=:a, last_error=:e, updated_at=now() "
                "WHERE id=:id"
            ),
            {"id": str(entry_id), "a": new_attempts, "e": error[:2000]},
        )
        row = session.execute(
            text("SELECT tenant_id, account_id, payload FROM outbox WHERE id=:id"),
            {"id": str(entry_id)},
        ).mappings().first()
        if row:
            session.execute(
                text(
                    "INSERT INTO dlq (tenant_id, account_id, source, ref_id, payload, error) "
                    "VALUES (:t, :a, 'outbox', :ref, CAST(:p AS jsonb), :e)"
                ),
                {
                    "t": str(row["tenant_id"]),
                    "a": str(row["account_id"]),
                    "ref": str(entry_id),
                    "p": _json(dict(row["payload"])),
                    "e": error[:2000],
                },
            )
        return
    backoff = timedelta(seconds=min(2 ** new_attempts, 300))
    session.execute(
        text(
            "UPDATE outbox SET status='PENDING', attempts=:a, last_error=:e, "
            "available_at = now() + :backoff, updated_at=now() WHERE id=:id"
        ),
        {"id": str(entry_id), "a": new_attempts, "e": error[:2000], "backoff": backoff},
    )


def reap_orphans(session: Session, *, stuck_minutes: int = 10) -> int:
    """Re-queue IN_PROGRESS rows whose worker died (cron reaper)."""
    res = session.execute(
        text(
            "UPDATE outbox SET status='PENDING', updated_at=now() "
            "WHERE status='IN_PROGRESS' AND updated_at < :cutoff"
        ),
        {"cutoff": now_utc() - timedelta(minutes=stuck_minutes)},
    )
    return res.rowcount or 0


def _json(obj: dict) -> str:
    import json

    return json.dumps(obj, default=str)
