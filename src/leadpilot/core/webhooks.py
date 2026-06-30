"""Inbound webhook effects: Razorpay billing lifecycle + Meta lead-form capture.

Both run pre-auth (the webhook has no tenant context), so they resolve the tenant from
a provider key (razorpay_subscription_id / Meta page_id) via the platform role, then
apply changes inside a tenant session.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from leadpilot.common.logging import get_logger
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.enums import (
    InvoiceStatus,
    LeadStatus,
    NotificationKind,
    SubscriptionStatus,
)
from leadpilot.core.models import Invoice, Lead, MetaConnection, Notification, Subscription
from leadpilot.core.money import with_gst
from leadpilot.integrations.razorpay.base import TIER_PRICE_PAISE

log = get_logger("webhooks")


def apply_razorpay_event(*, event: str, subscription_id: str,
                         period_end: datetime | None = None) -> bool:
    """Update the subscription + (on charge) write a GST invoice. Idempotent per period."""
    with platform_session() as s:
        row = s.execute(
            select(Subscription.tenant_id, Subscription.account_id)
            .where(Subscription.razorpay_subscription_id == subscription_id)
        ).first()
    if row is None:
        log.warning("razorpay_unknown_subscription", sub=subscription_id)
        return False
    tenant_id, account_id = row

    with tenant_session(tenant_id) as s:
        sub = s.scalar(
            select(Subscription).where(Subscription.razorpay_subscription_id == subscription_id))
        if sub is None:
            return False
        if event in ("subscription.charged", "subscription.activated"):
            sub.status = SubscriptionStatus.ACTIVE.value
            if period_end:
                sub.current_period_end = period_end
            base, gst, _total = with_gst(TIER_PRICE_PAISE.get(sub.tier, 0))
            period = (period_end or datetime.now(UTC)).strftime("%Y-%m")
            exists = s.scalar(select(Invoice).where(
                Invoice.account_id == account_id, Invoice.period == period))
            if exists is None:
                s.add(Invoice(tenant_id=tenant_id, account_id=account_id, amount_paise=base,
                              gst_paise=gst, status=InvoiceStatus.PAID.value, period=period))
        elif event in ("subscription.halted", "payment.failed"):
            sub.status = SubscriptionStatus.PAST_DUE.value
            s.add(Notification(tenant_id=tenant_id, account_id=account_id,
                               kind=NotificationKind.BILLING.value, title="Payment issue",
                               body="Your subscription payment failed. Please update your mandate."))
        elif event == "subscription.cancelled":
            sub.status = SubscriptionStatus.CANCELLED.value
    log.info("razorpay_event_applied", rzp_event=event, sub=subscription_id)
    return True


def capture_leadgen(*, page_id: str, leadgen_id: str, name: str | None,
                    phone: str | None) -> UUID | None:
    """Capture an Instant-Form (Lead Ads) lead into the inbox, resolving the account by
    page_id. Idempotent on leadgen_id (the source_creative_id slot carries it)."""
    with platform_session() as s:
        row = s.execute(
            select(MetaConnection.tenant_id, MetaConnection.account_id)
            .where(MetaConnection.page_id == page_id)
        ).first()
    if row is None:
        log.warning("leadgen_unrouted_page", page_id=page_id)
        return None
    tenant_id, account_id = row

    with tenant_session(tenant_id) as s:
        existing = s.scalar(select(Lead).where(
            Lead.account_id == account_id, Lead.wa_phone == (phone or leadgen_id)))
        if existing is not None:
            return existing.id
        lead = Lead(tenant_id=tenant_id, account_id=account_id, source_channel="META_LEADFORM",
                    wa_phone=phone or leadgen_id, name=name, status=LeadStatus.NEW.value,
                    first_msg_at=datetime.now(UTC), intent_summary="Submitted a lead form")
        s.add(lead)
        s.flush()
        s.add(Notification(tenant_id=tenant_id, account_id=account_id,
                           kind=NotificationKind.HOT_LEAD.value, title="New lead form",
                           body=f"{name or 'A customer'} submitted your lead form.", ref_id=lead.id))
        return lead.id
