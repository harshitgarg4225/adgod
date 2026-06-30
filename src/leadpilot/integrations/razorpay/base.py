"""Razorpay adapter (Subscriptions + UPI Autopay + GST), PRD §10.3.

Tier pricing (PRD §6.9 defaults, in paise). MOCK returns deterministic ids + a hosted
mandate URL so the billing flow is exercisable without a live Razorpay account.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

# Monthly platform fee per tier, in paise (₹ → paise).
TIER_PRICE_PAISE = {
    "STARTER": 149900,   # ₹1,499
    "GROWTH": 349900,    # ₹3,499
    "PRO": 699900,       # ₹6,999
}
TRIAL_DAYS = 7


@dataclass(slots=True)
class SubscriptionResult:
    razorpay_subscription_id: str
    short_url: str        # hosted UPI-mandate authorization URL
    status: str


class RazorpayAdapter:
    def create_subscription(self, *, tier: str, account_id: str) -> SubscriptionResult:
        raise NotImplementedError

    @staticmethod
    def verify_webhook(payload: bytes, signature: str | None, secret: str) -> bool:
        if not signature or not secret:
            return False
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
