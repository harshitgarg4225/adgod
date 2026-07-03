"""BFF request/response models (owner-simple shapes)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OtpRequest(BaseModel):
    phone: str


class OtpVerify(BaseModel):
    phone: str
    code: str


class RefreshRequest(BaseModel):
    refresh: str


class UserOut(BaseModel):
    id: UUID
    name: str | None
    role: str
    account_id: UUID | None
    locale: str


class TokenOut(BaseModel):
    access: str
    refresh: str
    user: UserOut


class AccessOut(BaseModel):
    access: str


class LeadListItem(BaseModel):
    id: UUID
    name: str | None
    intent_summary: str | None
    score: str | None
    status: str
    source_channel: str
    owner_action: str
    created_at: datetime
    first_msg_at: datetime | None


class MessageOut(BaseModel):
    direction: str
    type: str
    body: str | None
    status: str
    created_at: datetime


class LeadDetailOut(BaseModel):
    id: UUID
    name: str | None
    wa_phone: str
    score: str | None
    status: str
    intent_summary: str | None
    budget_signal: str | None
    timeline_signal: str | None
    location_signal: str | None
    owner_action: str
    source_channel: str
    created_at: datetime
    qualified_at: datetime | None
    transcript: list[MessageOut]
    # False on the own-number path (no Cloud API) — the UI hides the reply composer.
    can_message: bool = False


class LeadPatch(BaseModel):
    owner_action: str | None = None
    status: str | None = None


class HomeOut(BaseModel):
    today_spend_paise: int
    today_spend_display: str
    enquiries_today: int
    qualified_today: int
    cpql_paise: int | None
    cpql_display: str | None
    campaign_status: list[str]
    # Owner-control + Saathi presence (drives the dashboard's home experience).
    phase: str
    autopilot_level: str
    paused: bool
    daily_budget_paise: int
    daily_budget_display: str
    saathi_status: str
    unread_notifications: int
    spend_trend: list[int] = []  # last 7 days spend in paise, for the sparkline


class NotificationOut(BaseModel):
    id: UUID
    kind: str
    title: str | None
    body: str | None
    ref_id: UUID | None
    read_at: datetime | None
    created_at: datetime
