"""Billing: tiers, UPI-Autopay subscription, invoices (PRD §6.9, §9.6)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from leadpilot.bff.deps import Principal, current_principal
from leadpilot.common.errors import NotFoundError, ValidationError
from leadpilot.core.db import tenant_session
from leadpilot.core.enums import SubscriptionStatus, SubscriptionTier
from leadpilot.core.models import Invoice, Subscription
from leadpilot.core.money import format_paise, with_gst
from leadpilot.integrations.razorpay import get_razorpay_adapter
from leadpilot.integrations.razorpay.base import TIER_PRICE_PAISE, TRIAL_DAYS

router = APIRouter(prefix="/billing", tags=["billing"])


class SubscribeIn(BaseModel):
    tier: str


@router.post("/subscribe")
def subscribe(body: SubscribeIn, principal: Principal = Depends(current_principal)) -> dict:
    tier = body.tier.upper()
    if tier not in {t.value for t in SubscriptionTier}:
        raise ValidationError(f"Unknown tier: {tier}")
    if not principal.account_id:
        raise NotFoundError("No account")

    result = get_razorpay_adapter().create_subscription(tier=tier, account_id=principal.account_id)
    base, gst, total = with_gst(TIER_PRICE_PAISE[tier])

    with tenant_session(principal.tenant_id) as s:
        sub = s.scalar(select(Subscription).where(Subscription.account_id == principal.account_id))
        trial_end = datetime.now(UTC) + timedelta(days=TRIAL_DAYS)
        if sub is None:
            sub = Subscription(tenant_id=principal.tenant_id, account_id=principal.account_id)
            s.add(sub)
        sub.tier = tier
        sub.status = SubscriptionStatus.TRIAL.value
        sub.razorpay_subscription_id = result.razorpay_subscription_id
        sub.trial_end = trial_end

    return {
        "tier": tier,
        "price_paise": base, "gst_paise": gst, "total_paise": total,
        "price_display": format_paise(total),
        "mandate_url": result.short_url,
        "razorpay_subscription_id": result.razorpay_subscription_id,
        "trial_days": TRIAL_DAYS,
    }


@router.get("/subscription")
def get_subscription(principal: Principal = Depends(current_principal)) -> dict:
    if not principal.account_id:
        raise NotFoundError("No account")
    with tenant_session(principal.tenant_id) as s:
        sub = s.scalar(select(Subscription).where(Subscription.account_id == principal.account_id))
        if sub is None:
            return {"status": "NONE"}
        return {"tier": sub.tier, "status": sub.status,
                "trial_end": sub.trial_end.isoformat() if sub.trial_end else None,
                "current_period_end": sub.current_period_end.isoformat()
                if sub.current_period_end else None}


@router.get("/invoices")
def invoices(principal: Principal = Depends(current_principal)) -> list[dict]:
    if not principal.account_id:
        raise NotFoundError("No account")
    with tenant_session(principal.tenant_id) as s:
        rows = s.scalars(
            select(Invoice).where(Invoice.account_id == principal.account_id)
            .order_by(Invoice.created_at.desc())
        ).all()
        return [{"id": str(i.id), "amount_paise": i.amount_paise, "gst_paise": i.gst_paise,
                 "status": i.status, "pdf_url": i.pdf_url, "period": i.period} for i in rows]


@router.get("/tiers")
def tiers() -> list[dict]:
    out = []
    for t in SubscriptionTier:
        base, gst, total = with_gst(TIER_PRICE_PAISE[t.value])
        out.append({"tier": t.value, "price_paise": base, "gst_paise": gst,
                    "total_paise": total, "price_display": format_paise(total)})
    return out
