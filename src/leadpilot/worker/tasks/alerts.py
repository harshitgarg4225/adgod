"""Owner alerting: the owner lives on their phone, not in our app. A lead is perishable —
tell them the moment one arrives (SMS via the already-provisioned MSG91 account; a
WhatsApp utility template can join later for Cloud-API owners)."""
from __future__ import annotations

from sqlalchemy import select

from leadpilot.common.config import settings
from leadpilot.common.logging import get_logger, mask_phone
from leadpilot.common.ratelimit import enforce
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.integrations.otp.provider import send_lead_alert
from leadpilot.worker.celery_app import app

log = get_logger("task.alerts")


@app.task(name="leadpilot.alerts.lead_sms")
def lead_sms(tenant_id: str, account_id: str, lead_id: str) -> bool:
    """Best-effort SMS to the owner about a freshly captured lead. Capped per account per
    day (SMS costs money; a runaway loop must not burn the balance), fail-open on the
    limiter, and never raises — an alert failure must not requeue lead processing."""
    try:
        try:
            enforce("lead_sms", account_id, limit=settings.sms_alert_daily_cap,
                    window_s=86400)
        except Exception:  # over the cap (or limiter down + fail-closed) → skip quietly
            log.info("lead_sms_capped", account=account_id)
            return False
        from leadpilot.core.models import Lead, User

        with platform_session() as s:
            owner_phone = s.scalar(select(User.phone).where(
                User.account_id == account_id, User.role == "OWNER"))
        if not owner_phone:
            return False
        with tenant_session(tenant_id) as s:
            lead = s.get(Lead, lead_id)
            if lead is None:
                return False
            name, phone = lead.name, lead.wa_phone
        ok = send_lead_alert(phone=owner_phone, lead_name=name or "New lead",
                             lead_phone=phone or "")
        log.info("lead_sms", account=account_id, to=mask_phone(owner_phone), sent=ok)
        return ok
    except Exception as exc:  # noqa: BLE001
        log.warning("lead_sms_error", account=account_id, error=str(exc)[:150])
        return False


def enqueue_lead_alert(tenant_id, account_id, lead_id) -> None:
    """Fire-and-forget enqueue — callable from webhook threads and workers alike."""
    try:
        app.send_task("leadpilot.alerts.lead_sms",
                      args=[str(tenant_id), str(account_id), str(lead_id)], queue="agent")
    except Exception as exc:  # noqa: BLE001 - a broker hiccup must not break intake
        log.warning("lead_alert_enqueue_failed", error=str(exc)[:120])
