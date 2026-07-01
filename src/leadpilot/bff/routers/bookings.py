"""Bookings: turn a qualified lead into a scheduled appointment/callback (PRD §6 — the
core SMB job, 'fill my calendar'). Owner-driven today; the Closer can also propose a
booking autonomously (orchestrator BOOK transition)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from leadpilot.bff.deps import Principal, current_principal, require_account_access
from leadpilot.common.errors import NotFoundError, ValidationError
from leadpilot.core.db import tenant_session
from leadpilot.core.enums import LeadStatus
from leadpilot.core.models import Booking, Lead

router = APIRouter(tags=["bookings"])

_STATUSES = {"PROPOSED", "CONFIRMED", "CANCELLED", "COMPLETED"}


class BookingOut(BaseModel):
    id: str
    lead_id: str
    lead_name: str | None
    lead_phone: str | None
    slot_start: datetime | None
    slot_end: datetime | None
    status: str
    calendar_ref: str | None


class BookIn(BaseModel):
    slot_start: datetime | None = None
    slot_end: datetime | None = None
    calendar_ref: str | None = None


def _to_out(b: Booking, lead: Lead | None) -> BookingOut:
    return BookingOut(
        id=str(b.id), lead_id=str(b.lead_id),
        lead_name=lead.name if lead else None,
        lead_phone=lead.wa_phone if lead else None,
        slot_start=b.slot_start, slot_end=b.slot_end,
        status=b.status, calendar_ref=b.calendar_ref,
    )


@router.get("/accounts/{account_id}/bookings", response_model=list[BookingOut])
def list_bookings(
    account_id: str, principal: Principal = Depends(current_principal)
) -> list[BookingOut]:
    require_account_access(principal, account_id)
    with tenant_session(principal.tenant_id) as s:
        rows = s.scalars(
            select(Booking).where(Booking.account_id == account_id)
            .order_by(Booking.slot_start.desc().nullslast(), Booking.created_at.desc())
        ).all()
        leads = {
            row.id: row
            for row in s.scalars(
                select(Lead).where(Lead.id.in_([b.lead_id for b in rows]))
            ).all()
        } if rows else {}
        return [_to_out(b, leads.get(b.lead_id)) for b in rows]


@router.post("/leads/{lead_id}/book", response_model=BookingOut)
def book_lead(
    lead_id: str, body: BookIn, principal: Principal = Depends(current_principal)
) -> BookingOut:
    """Owner books an appointment/callback with a lead. Idempotent-ish: reuses an open
    (non-cancelled) booking for the lead instead of stacking duplicates."""
    with tenant_session(principal.tenant_id) as s:
        lead = s.get(Lead, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        require_account_access(principal, str(lead.account_id))
        booking = s.scalar(
            select(Booking).where(Booking.lead_id == lead.id, Booking.status != "CANCELLED")
            .order_by(Booking.created_at.desc())
        )
        if booking is None:
            booking = Booking(tenant_id=lead.tenant_id, account_id=lead.account_id, lead_id=lead.id)
            s.add(booking)
        booking.slot_start = body.slot_start or booking.slot_start
        booking.slot_end = body.slot_end or booking.slot_end
        booking.calendar_ref = body.calendar_ref or booking.calendar_ref
        booking.status = "CONFIRMED"
        lead.status = LeadStatus.BOOKED.value
        lead.booked_at = _now()
        s.flush()
        return _to_out(booking, lead)


class BookingPatch(BaseModel):
    status: str


@router.patch("/bookings/{booking_id}", response_model=BookingOut)
def update_booking(
    booking_id: str, patch: BookingPatch, principal: Principal = Depends(current_principal)
) -> BookingOut:
    if patch.status not in _STATUSES:
        raise ValidationError(f"Invalid booking status: {patch.status}")
    with tenant_session(principal.tenant_id) as s:
        booking = s.get(Booking, booking_id)
        if booking is None:
            raise NotFoundError("Booking not found")
        require_account_access(principal, str(booking.account_id))
        booking.status = patch.status
        lead = s.get(Lead, booking.lead_id)
        return _to_out(booking, lead)


def _now() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)
