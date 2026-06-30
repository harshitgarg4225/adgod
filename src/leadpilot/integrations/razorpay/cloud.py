"""Real Razorpay transport. Used when MOCK_RAZORPAY=false.

Creates a Subscription against a per-tier Plan and returns the hosted authorization
(UPI Autopay mandate) URL. Plan ids are provisioned out of band and mapped by tier.
"""
from __future__ import annotations

import httpx

from leadpilot.common.config import settings
from leadpilot.integrations.razorpay.base import RazorpayAdapter, SubscriptionResult

_API = "https://api.razorpay.com/v1"


class CloudRazorpayAdapter(RazorpayAdapter):  # pragma: no cover - requires live creds
    def __init__(self, plan_ids: dict[str, str] | None = None) -> None:
        self._auth = (settings.razorpay_key_id or "", settings.razorpay_key_secret or "")
        self._plan_ids = plan_ids or {}
        self._client = httpx.Client(timeout=20.0, auth=self._auth)

    def create_subscription(self, *, tier: str, account_id: str) -> SubscriptionResult:
        plan_id = self._plan_ids.get(tier)
        resp = self._client.post(f"{_API}/subscriptions", json={
            "plan_id": plan_id, "total_count": 12, "customer_notify": 1,
            "notes": {"account_id": account_id},
        })
        resp.raise_for_status()
        data = resp.json()
        return SubscriptionResult(
            razorpay_subscription_id=data["id"],
            short_url=data.get("short_url", ""), status=data.get("status", "created"),
        )
