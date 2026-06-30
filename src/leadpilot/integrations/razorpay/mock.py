from __future__ import annotations

import hashlib

from leadpilot.common.config import settings
from leadpilot.integrations.razorpay.base import RazorpayAdapter, SubscriptionResult


class MockRazorpayAdapter(RazorpayAdapter):
    def create_subscription(self, *, tier: str, account_id: str) -> SubscriptionResult:
        sid = "sub_MOCK" + hashlib.sha256(f"{account_id}:{tier}".encode()).hexdigest()[:14]
        return SubscriptionResult(
            razorpay_subscription_id=sid,
            short_url=f"{settings.app_base_url}/billing/mandate/{sid}",
            status="created",
        )
