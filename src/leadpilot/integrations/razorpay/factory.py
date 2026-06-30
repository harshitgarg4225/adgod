from __future__ import annotations

from leadpilot.common.config import settings
from leadpilot.integrations.razorpay.base import RazorpayAdapter

_adapter: RazorpayAdapter | None = None


def get_razorpay_adapter() -> RazorpayAdapter:
    global _adapter
    if _adapter is None:
        if settings.mock_razorpay:
            from leadpilot.integrations.razorpay.mock import MockRazorpayAdapter

            _adapter = MockRazorpayAdapter()
        else:  # pragma: no cover
            from leadpilot.integrations.razorpay.cloud import CloudRazorpayAdapter

            _adapter = CloudRazorpayAdapter()
    return _adapter
