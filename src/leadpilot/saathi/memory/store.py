"""Saathi memory (PRD §4.4).

Structured memory lives in relational ledgers (creatives.perf, angles.qualified_lead_rate).
Semantic memory uses pgvector: creative embeddings retrieved by cosine similarity, scoped
by tenant (RLS). Cross-account priors are aggregated vertical+city signals gated by
k-anonymity (k ≥ 20 accounts) so no single tenant's data leaks.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from leadpilot.core.db import platform_session
from leadpilot.core.models import Creative
from leadpilot.saathi.providers.embeddings import get_embedding_provider

K_ANON = 20


def embed_creative(session: Session, creative: Creative) -> None:
    """Compute + store the embedding for a creative (PII-free ad copy)."""
    blob = " ".join(filter(None, [creative.headline, creative.primary_text, creative.description]))
    creative.embedding = get_embedding_provider().embed(blob)


def retrieve_winning_creatives(
    session: Session, *, account_id: UUID, query_text: str, k: int = 3
) -> list[Creative]:
    """Top-k past creatives most similar to `query_text` (tenant-scoped via RLS)."""
    vec = get_embedding_provider().embed(query_text)
    rows = session.scalars(
        select(Creative)
        .where(Creative.account_id == account_id, Creative.embedding.isnot(None))
        .order_by(Creative.embedding.cosine_distance(vec))
        .limit(k)
    ).all()
    return list(rows)


def vertical_city_priors(category: str, city: str) -> dict:
    """Aggregated, anonymized prior for a vertical+city, gated by k-anonymity.

    Runs via the platform role (cross-tenant) and returns a signal ONLY when at least
    K_ANON distinct accounts contributed — otherwise empty (no leakage).
    """
    with platform_session() as s:
        row = s.execute(
            text(
                """
                SELECT count(DISTINCT a.id) AS n,
                       avg(NULLIF(i.cpql_paise, 0)) AS avg_cpql
                FROM accounts a
                JOIN ad_insights i ON i.account_id = a.id
                WHERE a.category = :category
                  AND lower(coalesce((
                      SELECT bp.service_area_city FROM business_profiles bp
                      WHERE bp.account_id = a.id LIMIT 1), '')) = lower(:city)
                """
            ),
            {"category": category, "city": city},
        ).mappings().first()
    if not row or (row["n"] or 0) < K_ANON:
        return {"available": False, "k": row["n"] if row else 0, "k_required": K_ANON}
    return {"available": True, "k": row["n"], "avg_cpql_paise": int(row["avg_cpql"] or 0)}
