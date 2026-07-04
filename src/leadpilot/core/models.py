"""SQLAlchemy ORM models for the v1 walking-skeleton tables.

Mirrors PRD §8. Only the tables the core loop touches are modelled here; the
remaining end-state tables are created by migrations in later phases. Money is
integer paise. Timestamps are timezone-aware. Tenant-private tables carry
`tenant_id` and are RLS-forced (see migration 0001).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ─────────────────────────── Identity & account ───────────────────────────

class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="DIRECT")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    phase: Mapped[str] = mapped_column(String(30), nullable=False, default="SIGNED_UP")
    autopilot_level: Mapped[str] = mapped_column(String(20), nullable=False, default="ASSISTED")
    trust_score: Mapped[int] = mapped_column(Integer, default=0)
    default_language: Mapped[str] = mapped_column(String(8), nullable=False, default="hi")
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Kolkata")
    target_cpql_paise: Mapped[int] = mapped_column(BigInteger, default=20000)
    created_via: Mapped[str | None] = mapped_column(String(40))
    # Autopilot-with-veto: creatives auto-approve this many hours after generation on the
    # ASSISTED level (0 = wait for the owner forever). FULL skips approval entirely;
    # MANUAL never auto-approves.
    auto_approve_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    # Pause provenance: who paused (owner/trial/emergency/admin) decides who may resume
    # (e.g. a payment un-pauses trial pauses but never an owner's deliberate pause), and
    # which phase to restore.
    pause_reason: Mapped[str | None] = mapped_column(String(20))
    phase_before_pause: Mapped[str | None] = mapped_column(String(30))
    # India B2B invoicing details (GST-compliant invoices).
    gstin: Mapped[str | None] = mapped_column(String(20))
    legal_name: Mapped[str | None] = mapped_column(String(200))
    billing_address: Mapped[str | None] = mapped_column(Text)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="OWNER")
    name: Mapped[str | None] = mapped_column(String(200))
    locale: Mapped[str] = mapped_column(String(8), default="hi")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Bumped on logout / password-equivalent change to revoke all outstanding JWTs.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # DPDP: timestamp of the consent captured at signup.
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BusinessProfile(Base, TimestampMixin):
    __tablename__ = "business_profiles"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    offer: Mapped[str | None] = mapped_column(Text)
    service_area_city: Mapped[str | None] = mapped_column(String(80))
    service_radius_km: Mapped[int] = mapped_column(Integer, default=10)
    daily_budget_paise: Mapped[int] = mapped_column(BigInteger, default=50000)
    monthly_cap_paise: Mapped[int | None] = mapped_column(BigInteger)
    website_url: Mapped[str | None] = mapped_column(String(400))
    instagram_handle: Mapped[str | None] = mapped_column(String(120))
    gbp_url: Mapped[str | None] = mapped_column(String(400))
    raw_inputs: Mapped[dict] = mapped_column(JSONB, default=dict)


# ─────────────────────────── Integrations ───────────────────────────

class WhatsAppConnection(Base, TimestampMixin):
    __tablename__ = "whatsapp_connections"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="APP_DESTINATION")
    waba_id: Mapped[str | None] = mapped_column(String(60))
    phone_number_id: Mapped[str | None] = mapped_column(String(60))
    display_phone: Mapped[str | None] = mapped_column(String(20))
    verified_name_status: Mapped[str | None] = mapped_column(String(30))
    quality_rating: Mapped[str | None] = mapped_column(String(20))


class MetaConnection(Base, TimestampMixin):
    __tablename__ = "meta_connections"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    meta_business_id: Mapped[str | None] = mapped_column(String(60))
    ad_account_id: Mapped[str | None] = mapped_column(String(60))
    page_id: Mapped[str | None] = mapped_column(String(60))
    pixel_id: Mapped[str | None] = mapped_column(String(60))
    system_user_token_enc: Mapped[str | None] = mapped_column(Text)  # encrypted at rest
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")


class WaRoute(Base):
    """Routing layer (NOT RLS-bound): phone_number_id → tenant/account.

    Lets webhook-intake resolve the tenant BEFORE setting the GUC. Holds only
    routing keys, no secrets or lead PII.
    """

    __tablename__ = "wa_routes"
    id: Mapped[uuid.UUID] = _uuid_pk()
    phone_number_id: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ─────────────────────────── Campaign & creative (minimal for attribution) ───────────────────────────

class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    meta_campaign_id: Mapped[str | None] = mapped_column(String(60))
    objective: Mapped[str | None] = mapped_column(String(60))
    channel: Mapped[str] = mapped_column(String(20), default="META_CTWA")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    daily_budget_paise: Mapped[int] = mapped_column(BigInteger, default=50000)
    strategy: Mapped[dict] = mapped_column(JSONB, default=dict)


class Creative(Base, TimestampMixin):
    __tablename__ = "creatives"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    angle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    language: Mapped[str] = mapped_column(String(8), default="hi")
    format: Mapped[str] = mapped_column(String(20), default="IMAGE_VERTICAL")
    primary_text: Mapped[str | None] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(300))
    asset_url: Mapped[str | None] = mapped_column(String(500))
    thumb_url: Mapped[str | None] = mapped_column(String(500))
    compliance_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    compliance_notes: Mapped[str | None] = mapped_column(Text)
    approval_status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    hypothesis: Mapped[str | None] = mapped_column(Text)
    perf: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))


# ─────────────────────────── Leads & conversations ───────────────────────────

class Lead(Base, TimestampMixin):
    __tablename__ = "leads"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_channel: Mapped[str] = mapped_column(String(20), default="META_CTWA")
    source_campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_creative_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # Meta Instant-Form lead id — dedup key for webhook + polling intake (never a phone).
    leadgen_id: Mapped[str | None] = mapped_column(String(60), index=True)
    wa_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="NEW")
    score: Mapped[str | None] = mapped_column(String(8))
    intent_summary: Mapped[str | None] = mapped_column(Text)
    budget_signal: Mapped[str | None] = mapped_column(String(120))
    timeline_signal: Mapped[str | None] = mapped_column(String(120))
    location_signal: Mapped[str | None] = mapped_column(String(120))
    owner_action: Mapped[str] = mapped_column(String(16), default="NONE")
    first_msg_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    conversation: Mapped[Conversation] = relationship(back_populates="lead", uselist=False)

    __table_args__ = (
        UniqueConstraint("account_id", "wa_phone", "first_msg_at", name="uq_lead_dedupe"),
    )


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), default="WHATSAPP")
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="GREET")
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    free_window_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lead: Mapped[Lead] = relationship(back_populates="conversation")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", order_by="Message.created_at"
    )


class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(4), nullable=False)
    wa_message_id: Mapped[str | None] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(16), default="TEXT")
    body: Mapped[str | None] = mapped_column(Text)
    template_name: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="QUEUED")
    cost_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    redacted_body: Mapped[str | None] = mapped_column(Text)  # PII-scrubbed copy for memory

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class LeadQualification(Base, TimestampMixin):
    __tablename__ = "lead_qualifications"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True
    )
    score: Mapped[str] = mapped_column(String(8), nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, default=list)
    captured: Mapped[dict] = mapped_column(JSONB, default=dict)
    model_version: Mapped[str | None] = mapped_column(String(60))


# ─────────────────────────── Agent operations ───────────────────────────

class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    agent: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger: Mapped[str | None] = mapped_column(String(40))
    input_ref: Mapped[str | None] = mapped_column(String(120))
    output: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="OK")
    model: Mapped[str | None] = mapped_column(String(60))
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_paise: Mapped[int] = mapped_column(BigInteger, default=0)


class GuardrailEvent(Base, TimestampMixin):
    __tablename__ = "guardrail_events"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="INFO")
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    action_taken: Mapped[str | None] = mapped_column(String(60))


# ─────────────────────────── Durability (Temporal replacement) ───────────────────────────

class InboundEvent(Base):
    """Idempotent webhook intake. Unique on (provider, external_id)."""

    __tablename__ = "inbound_events"
    id: Mapped[uuid.UUID] = _uuid_pk()
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_inbound_event"),
    )


class Job(Base):
    """Run ledger keyed by (account, window) so a missed/overlapping run is a no-op."""

    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_job_dedupe"),)


class OutboxEntry(Base):
    """Intended external EFFECT, committed in the same txn as state.

    Keyed by (account_id, step_id) so a replay is a no-op (exactly-once effect).
    """

    __tablename__ = "outbox"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    step_id: Mapped[str] = mapped_column(String(200), nullable=False)
    effect_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(
        String(12), default="PENDING", server_default="PENDING", index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("account_id", "step_id", name="uq_outbox_step"),
        CheckConstraint("attempts >= 0", name="ck_outbox_attempts"),
    )


class DlqEntry(Base):
    __tablename__ = "dlq"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdempotencyKey(Base):
    """Persisted Idempotency-Key results for API writes."""

    __tablename__ = "idempotency_keys"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_code: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Tenant-scoped uniqueness: a key chosen by one tenant can neither collide with nor
    # leak another tenant's stored response.
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_idempotency_tenant_key"),)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ─────────────────────────── Research & creative (Scout/Maker) ───────────────────────────

class BusinessBrief(Base, TimestampMixin):
    __tablename__ = "business_briefs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    offer: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[list] = mapped_column(JSONB, default=list)
    usp: Mapped[list] = mapped_column(JSONB, default=list)
    objections: Mapped[list] = mapped_column(JSONB, default=list)
    tone: Mapped[str | None] = mapped_column(String(200))
    source_refs: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Angle(Base, TimestampMixin):
    __tablename__ = "angles"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    brief_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE")
    qualified_lead_rate: Mapped[float | None] = mapped_column(Float)


# ─────────────────────────── Campaign hierarchy (Buyer) ───────────────────────────

class AdSet(Base, TimestampMixin):
    __tablename__ = "ad_sets"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    meta_adset_id: Mapped[str | None] = mapped_column(String(60))
    name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(16), default="PROSPECTING")
    targeting: Mapped[dict] = mapped_column(JSONB, default=dict)
    budget_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")


class Ad(Base, TimestampMixin):
    __tablename__ = "ads"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    ad_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    meta_ad_id: Mapped[str | None] = mapped_column(String(60))
    creative_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")
    review_status: Mapped[str | None] = mapped_column(String(20))


class Audience(Base, TimestampMixin):
    __tablename__ = "audiences"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), default="SAVED")
    meta_audience_id: Mapped[str | None] = mapped_column(String(60))
    spec: Mapped[dict] = mapped_column(JSONB, default=dict)


class AdInsight(Base):
    """Per-level performance rows (partition-friendly by date). CPQL is joined from leads."""

    __tablename__ = "ad_insights"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    spend_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    impressions: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    frequency: Mapped[float] = mapped_column(Float, default=0.0)
    leads: Mapped[int] = mapped_column(Integer, default=0)
    qualified_leads: Mapped[int] = mapped_column(Integer, default=0)
    cpl_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    cpql_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OptimizationDecision(Base):
    __tablename__ = "optimization_decisions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    level: Mapped[str] = mapped_column(String(10))
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(60))
    before: Mapped[dict] = mapped_column(JSONB, default=dict)
    after: Mapped[dict] = mapped_column(JSONB, default=dict)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Approval(Base, TimestampMixin):
    __tablename__ = "approvals"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="PENDING")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ─────────────────────────── Billing ───────────────────────────

class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    tier: Mapped[str] = mapped_column(String(12), default="GROWTH")
    status: Mapped[str] = mapped_column(String(12), default="TRIAL")
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(60))
    mandate_id: Mapped[str | None] = mapped_column(String(60))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    razorpay_invoice_id: Mapped[str | None] = mapped_column(String(60))
    amount_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    gst_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(12), default="DRAFT")
    pdf_url: Mapped[str | None] = mapped_column(String(500))
    period: Mapped[str | None] = mapped_column(String(20))


class WalletLedger(Base):
    __tablename__ = "wallet_ledger"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(12), nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ref: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WaTemplate(Base, TimestampMixin):
    __tablename__ = "wa_templates"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="hi")
    category: Mapped[str] = mapped_column(String(16), default="UTILITY")
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="DRAFT")
    meta_template_id: Mapped[str | None] = mapped_column(String(60))


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    slot_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    slot_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="PROPOSED")
    calendar_ref: Mapped[str | None] = mapped_column(String(120))


# ─────────────────────────── Admin / ops (non-RLS, platform-scoped) ───────────────────────────

class AuditLog(Base):
    """Audited admin/agent/system actions (PRD §8.5). Cross-tenant → not RLS-bound."""

    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(80))
    before: Mapped[dict] = mapped_column(JSONB, default=dict)
    after: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    id: Mapped[uuid.UUID] = _uuid_pk()
    key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class AuthOtp(Base):
    """Phone OTP challenge (PRD §8.1). Non-RLS — verified before any tenant context."""

    __tablename__ = "auth_otps"
    id: Mapped[uuid.UUID] = _uuid_pk()
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    salt: Mapped[str | None] = mapped_column(String(64))  # per-code random salt
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# Tables that are RLS-forced (carry tenant_id; subject to the app.tenant_id policy).
# Intentionally NOT RLS:
#   * infra: outbox, jobs, dlq, inbound_events, idempotency_keys, wa_routes, tenants
#     (drained/scanned cross-tenant by the reaper and routing layer; no lead PII)
#   * users: the identity table is looked up by globally-unique phone during login,
#     BEFORE any tenant context exists. Lead/message PII stays strictly RLS.
RLS_TABLES = [
    "users",
    "accounts", "business_profiles", "whatsapp_connections", "meta_connections",
    "campaigns", "creatives", "leads", "conversations", "messages", "lead_qualifications",
    "agent_runs", "guardrail_events", "notifications",
    "business_briefs", "angles", "ad_sets", "ads", "audiences", "ad_insights",
    "optimization_decisions", "approvals", "subscriptions", "invoices", "wallet_ledger",
    "bookings",
]
