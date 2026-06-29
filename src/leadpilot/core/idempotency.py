"""Idempotency-Key handling for API writes (PRD §9).

A write carrying `Idempotency-Key` is recorded with a hash of its body. A replay
with the same key + same body returns the stored response; same key + different
body is a 409 conflict.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def hash_request(body: Any) -> str:
    raw = json.dumps(body, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def lookup(session: Session, key: str) -> dict | None:
    row = session.execute(
        text("SELECT request_hash, response_code, response_body FROM idempotency_keys WHERE key=:k"),
        {"k": key},
    ).mappings().first()
    return dict(row) if row else None


def store(
    session: Session,
    *,
    key: str,
    request_hash: str,
    response_code: int,
    response_body: dict,
    tenant_id: str | None = None,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO idempotency_keys (tenant_id, key, request_hash, response_code, response_body)
            VALUES (:t, :k, :h, :c, CAST(:b AS jsonb))
            ON CONFLICT (key) DO NOTHING
            """
        ),
        {
            "t": tenant_id,
            "k": key,
            "h": request_hash,
            "c": response_code,
            "b": json.dumps(response_body, default=str),
        },
    )
