"""Routing + idempotent intake (runs BEFORE a tenant context exists).

Webhooks arrive unauthenticated; we resolve the tenant from a routing key
(phone_number_id) via the non-RLS `wa_routes` table, then everything downstream
runs inside `tenant_session`. `record_inbound_event` makes intake idempotent on
(provider, external_id) so a Meta re-delivery is a no-op.
"""
from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import text

from leadpilot.core.db import platform_session


def resolve_wa_route(phone_number_id: str) -> tuple[UUID, UUID] | None:
    """phone_number_id → (tenant_id, account_id) or None if unrouted."""
    with platform_session() as session:
        row = session.execute(
            text("SELECT tenant_id, account_id FROM wa_routes WHERE phone_number_id = :p"),
            {"p": phone_number_id},
        ).mappings().first()
    if not row:
        return None
    return UUID(str(row["tenant_id"])), UUID(str(row["account_id"]))


def record_inbound_event(
    *, provider: str, external_id: str, tenant_id: UUID | None,
    account_id: UUID | None, payload: dict,
) -> UUID | None:
    """Insert idempotently. Returns the new row id, or None if already seen."""
    with platform_session() as session:
        row = session.execute(
            text(
                """
                INSERT INTO inbound_events (provider, external_id, tenant_id, account_id, payload)
                VALUES (:provider, :external_id, :tenant_id, :account_id, CAST(:payload AS jsonb))
                ON CONFLICT (provider, external_id) DO NOTHING
                RETURNING id
                """
            ),
            {
                "provider": provider,
                "external_id": external_id,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "account_id": str(account_id) if account_id else None,
                "payload": json.dumps(payload, default=str),
            },
        ).first()
    return UUID(str(row[0])) if row else None


def load_inbound_event(event_id: UUID) -> dict | None:
    with platform_session() as session:
        row = session.execute(
            text(
                "SELECT id, provider, external_id, tenant_id, account_id, payload "
                "FROM inbound_events WHERE id = :id"
            ),
            {"id": str(event_id)},
        ).mappings().first()
    return dict(row) if row else None


def mark_inbound_processed(event_id: UUID) -> None:
    with platform_session() as session:
        session.execute(
            text("UPDATE inbound_events SET processed_at = now() WHERE id = :id"),
            {"id": str(event_id)},
        )
