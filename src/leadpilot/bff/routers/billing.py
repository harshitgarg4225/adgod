"""Billing: tiers, UPI-Autopay subscription, invoices (PRD §6.9, §9.6)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from html import escape

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select

from leadpilot.bff.deps import Principal, current_principal
from leadpilot.common.errors import NotFoundError, ValidationError
from leadpilot.core.db import tenant_session
from leadpilot.core.enums import SubscriptionStatus, SubscriptionTier, WalletEntryType
from leadpilot.core.models import Account, Invoice, Subscription, WalletLedger
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

    base, gst, total = with_gst(TIER_PRICE_PAISE[tier])

    # Idempotency: if this account already has a live (TRIAL/ACTIVE) subscription on the
    # same tier with a mandate, reuse it instead of creating a duplicate at Razorpay. This
    # makes the endpoint safe under client double-submit and outbox replay (no double
    # mandate / double charge).
    live = {SubscriptionStatus.TRIAL.value, SubscriptionStatus.ACTIVE.value}
    with tenant_session(principal.tenant_id) as s:
        sub = s.scalar(select(Subscription).where(Subscription.account_id == principal.account_id))
        existing_url = ""
        if (
            sub is not None
            and sub.tier == tier
            and sub.status in live
            and sub.razorpay_subscription_id
        ):
            return {
                "tier": tier,
                "price_paise": base, "gst_paise": gst, "total_paise": total,
                "price_display": format_paise(total),
                "mandate_url": existing_url,  # mandate already authorised/in-flight
                "razorpay_subscription_id": sub.razorpay_subscription_id,
                "trial_days": TRIAL_DAYS,
                "reused": True,
            }

        result = get_razorpay_adapter().create_subscription(
            tier=tier, account_id=principal.account_id
        )
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


class TopupIn(BaseModel):
    amount_paise: int


def _wallet_balance(s, account_id) -> int:
    last = s.scalar(
        select(WalletLedger).where(WalletLedger.account_id == account_id)
        .order_by(WalletLedger.created_at.desc()))
    return last.balance_paise if last else 0


@router.post("/wallet/topup")
def wallet_topup(body: TopupIn, principal: Principal = Depends(current_principal)) -> dict:
    """Top up the ad wallet (PRD §6.9.2, Pro). Funds are ledgered separately from platform
    fees. In mock mode the credit is immediate; with real Razorpay it lands on the order
    webhook. Wallet money never co-mingles with subscription revenue."""
    if body.amount_paise <= 0:
        raise ValidationError("amount must be positive")
    if not principal.account_id:
        raise NotFoundError("No account")
    with tenant_session(principal.tenant_id) as s:
        balance = _wallet_balance(s, principal.account_id) + body.amount_paise
        s.add(WalletLedger(tenant_id=principal.tenant_id, account_id=principal.account_id,
                           entry_type=WalletEntryType.TOPUP.value, amount_paise=body.amount_paise,
                           balance_paise=balance, ref="mock-topup"))
    return {"balance_paise": balance, "balance_display": format_paise(balance)}


@router.get("/wallet")
def wallet(principal: Principal = Depends(current_principal)) -> dict:
    if not principal.account_id:
        raise NotFoundError("No account")
    with tenant_session(principal.tenant_id) as s:
        balance = _wallet_balance(s, principal.account_id)
        rows = s.scalars(
            select(WalletLedger).where(WalletLedger.account_id == principal.account_id)
            .order_by(WalletLedger.created_at.desc()).limit(50)).all()
        ledger = [{"entry_type": r.entry_type, "amount_paise": r.amount_paise,
                   "balance_paise": r.balance_paise, "ref": r.ref,
                   "created_at": r.created_at.isoformat()} for r in rows]
    return {"balance_paise": balance, "balance_display": format_paise(balance), "ledger": ledger}


@router.get("/invoices/{invoice_id}/document", response_class=HTMLResponse)
def invoice_document(
    invoice_id: str, principal: Principal = Depends(current_principal)
) -> HTMLResponse:
    """A GST-compliant invoice as printable HTML (the browser saves it as PDF). Includes
    the buyer's GSTIN/legal name/address so it's valid for Indian B2B input-credit."""
    with tenant_session(principal.tenant_id) as s:
        inv = s.get(Invoice, invoice_id)
        if inv is None or (
            principal.account_id and str(inv.account_id) != principal.account_id
        ):
            raise NotFoundError("Invoice not found")
        account = s.get(Account, inv.account_id)
        buyer_name = escape((account.legal_name or account.business_name) if account else "")
        gstin = escape(account.gstin or "—") if account else "—"
        address = escape(account.billing_address or "—") if account else "—"
        base = inv.amount_paise
        gst = inv.gst_paise
        total = base + gst
        html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Invoice {escape(str(inv.id))[:8]}</title>
<style>
 body{{font-family:system-ui,sans-serif;color:#0F172A;max-width:640px;margin:32px auto;padding:0 20px}}
 h1{{color:#0B7A4B}} table{{width:100%;border-collapse:collapse;margin-top:16px}}
 td,th{{padding:8px;border-bottom:1px solid #E2E8F0;text-align:left}}
 .r{{text-align:right}} .muted{{color:#64748B;font-size:13px}} .tot{{font-weight:700}}
</style></head><body>
 <h1>Salmor</h1>
 <p class="muted">Tax Invoice · {escape(inv.period or "")} · Status: {escape(inv.status)}</p>
 <p><b>Billed to:</b> {buyer_name}<br><span class="muted">GSTIN: {gstin}<br>{address}</span></p>
 <table>
  <tr><th>Description</th><th class="r">Amount</th></tr>
  <tr><td>Salmor subscription</td><td class="r">{escape(format_paise(base))}</td></tr>
  <tr><td>GST @ 18%</td><td class="r">{escape(format_paise(gst))}</td></tr>
  <tr class="tot"><td>Total</td><td class="r">{escape(format_paise(total))}</td></tr>
 </table>
 <p class="muted">This is a computer-generated invoice.</p>
</body></html>"""
        return HTMLResponse(content=html)


@router.get("/tiers")
def tiers() -> list[dict]:
    out = []
    for t in SubscriptionTier:
        base, gst, total = with_gst(TIER_PRICE_PAISE[t.value])
        out.append({"tier": t.value, "price_paise": base, "gst_paise": gst,
                    "total_paise": total, "price_display": format_paise(total)})
    return out
