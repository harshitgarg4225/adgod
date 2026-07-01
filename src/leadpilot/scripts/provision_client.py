"""Provision a real client by hand — the review-free 'first few customers' path.

No Meta App Review and no WhatsApp WABA are required when you operate as an agency:
  * Ads run on a client ad account inside YOUR Meta Business Manager, authorised by a
    System User token you paste in (--meta-token). Manual/agency operation, not the
    self-serve OAuth flow that needs App Review.
  * WhatsApp uses APP_DESTINATION by default: the Click-to-WhatsApp ad opens the client's
    OWN existing WhatsApp number (--owner-phone) — no Cloud API, no template approval, no
    green-tick. Leads land in their WhatsApp; they (or you) reply. Add the automated AI
    qualifier later by switching to --wa-mode cloud with a real phone_number_id.

Usage (agency / own-number, review-free):
  python -m leadpilot.scripts.provision_client \
      --business "Verma Dental" --category clinic --city Indore \
      --owner-phone +919812345678 --daily-budget 500 --language hi \
      --meta-business 123 --ad-account 456 --page 789 --meta-token "EAAG..."

Then drive it: the autonomous progression cron (or the calls below) takes it
research → creative → launch. Prints the account id + login phone.
"""
from __future__ import annotations

import argparse
import uuid

from sqlalchemy import select

from leadpilot.common.crypto import encrypt
from leadpilot.common.logging import get_logger
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.enums import AccountPhase, AutopilotLevel, TenantType, UserRole, WhatsAppMode
from leadpilot.core.models import (
    Account,
    BusinessProfile,
    MetaConnection,
    Tenant,
    User,
    WaRoute,
    WhatsAppConnection,
)
from leadpilot.core.money import Paise

log = get_logger("provision")


def provision_client(
    *,
    business_name: str,
    category: str,
    city: str,
    owner_phone: str,
    owner_name: str | None = None,
    daily_budget_rupees: int = 500,
    language: str = "hi",
    autopilot: str = "ASSISTED",
    # Meta (agency: your System User token on the client's ad account)
    meta_business_id: str | None = None,
    ad_account_id: str | None = None,
    page_id: str | None = None,
    meta_token: str | None = None,
    # WhatsApp
    wa_mode: str = "APP_DESTINATION",
    phone_number_id: str | None = None,   # only for wa_mode=CLOUD_API
) -> dict:
    tenant_id, account_id, user_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    with platform_session() as s:
        s.add(Tenant(id=tenant_id, name=f"{business_name} (client)", type=TenantType.DIRECT.value,
                     status="ACTIVE", settings={}))
        s.add(User(id=user_id, tenant_id=tenant_id, account_id=account_id, phone=owner_phone,
                   role=UserRole.OWNER.value, name=owner_name, locale=language))
        # CLOUD_API needs a routing key so inbound webhooks resolve this tenant.
        if wa_mode == WhatsAppMode.CLOUD_API.value and phone_number_id:
            if s.scalar(select(WaRoute).where(WaRoute.phone_number_id == phone_number_id)) is None:
                s.add(WaRoute(phone_number_id=phone_number_id, tenant_id=tenant_id,
                              account_id=account_id))

    with tenant_session(tenant_id) as s:
        s.add(Account(id=account_id, tenant_id=tenant_id, business_name=business_name,
                      category=category, phase=AccountPhase.SIGNED_UP.value,
                      autopilot_level=autopilot, default_language=language,
                      timezone="Asia/Kolkata", target_cpql_paise=int(Paise.from_rupees(200)),
                      created_via="manual"))
        s.add(BusinessProfile(tenant_id=tenant_id, account_id=account_id, offer=business_name,
                              service_area_city=city, service_radius_km=10,
                              daily_budget_paise=int(Paise.from_rupees(daily_budget_rupees))))
        if ad_account_id and page_id:
            s.add(MetaConnection(
                tenant_id=tenant_id, account_id=account_id, meta_business_id=meta_business_id,
                ad_account_id=ad_account_id, page_id=page_id,
                system_user_token_enc=encrypt(meta_token) if meta_token else None,
                status="ACTIVE"))
        s.add(WhatsAppConnection(
            tenant_id=tenant_id, account_id=account_id, mode=wa_mode,
            phone_number_id=phone_number_id, display_phone=owner_phone,
            verified_name_status="APPROVED", quality_rating="GREEN"))

    log.info("client_provisioned", account=str(account_id), wa_mode=wa_mode)
    return {"tenant_id": str(tenant_id), "account_id": str(account_id),
            "owner_phone": owner_phone, "wa_mode": wa_mode}


def main() -> None:
    p = argparse.ArgumentParser(description="Provision a Salmor client (review-free agency path)")
    p.add_argument("--business", required=True)
    p.add_argument("--category", default="other")
    p.add_argument("--city", default="")
    p.add_argument("--owner-phone", required=True)
    p.add_argument("--owner-name", default=None)
    p.add_argument("--daily-budget", type=int, default=500, help="rupees/day")
    p.add_argument("--language", default="hi")
    p.add_argument("--autopilot", default="ASSISTED",
                   choices=[a.value for a in AutopilotLevel])
    p.add_argument("--meta-business", default=None)
    p.add_argument("--ad-account", default=None)
    p.add_argument("--page", default=None)
    p.add_argument("--meta-token", default=None, help="your System User token (agency)")
    p.add_argument("--wa-mode", default="APP_DESTINATION",
                   choices=[m.value for m in WhatsAppMode])
    p.add_argument("--phone-number-id", default=None, help="only for --wa-mode CLOUD_API")
    a = p.parse_args()

    out = provision_client(
        business_name=a.business, category=a.category, city=a.city,
        owner_phone=a.owner_phone, owner_name=a.owner_name, daily_budget_rupees=a.daily_budget,
        language=a.language, autopilot=a.autopilot, meta_business_id=a.meta_business,
        ad_account_id=a.ad_account, page_id=a.page, meta_token=a.meta_token,
        wa_mode=a.wa_mode, phone_number_id=a.phone_number_id)

    print("✓ Client provisioned")
    print(f"  account_id : {out['account_id']}")
    print(f"  owner login: {out['owner_phone']}  (they log in with phone OTP)")
    print(f"  whatsapp   : {out['wa_mode']}")
    print("  next: Saathi will research → create ads → launch (auto under FULL autopilot,")
    print("        or after you approve creatives under ASSISTED).")


if __name__ == "__main__":
    main()
