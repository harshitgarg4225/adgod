"""Seed a demo coaching-center account so the walking skeleton is runnable.

Idempotent: re-running leaves a single demo tenant/account/user/route in place.
Usage: python -m leadpilot.scripts.seed_demo
"""
from __future__ import annotations

from sqlalchemy import select

from leadpilot.common.logging import get_logger
from leadpilot.core.db import platform_session, tenant_session
from leadpilot.core.enums import AccountPhase, AutopilotLevel, UserRole, WhatsAppMode
from leadpilot.core.models import (
    Account,
    BusinessProfile,
    MetaConnection,
    Tenant,
    User,
    WaRoute,
    WaTemplate,
    WhatsAppConnection,
)
from leadpilot.core.money import Paise
from leadpilot.scripts.demo_constants import (
    DEMO_ACCOUNT_ID,
    DEMO_ADMIN_ID,
    DEMO_ADMIN_PHONE,
    DEMO_BUSINESS_NAME,
    DEMO_CATEGORY,
    DEMO_CITY,
    DEMO_LANGUAGE,
    DEMO_OWNER_PHONE,
    DEMO_PARTNER_PHONE,
    DEMO_PARTNER_TENANT_ID,
    DEMO_PARTNER_USER_ID,
    DEMO_PHONE_NUMBER_ID,
    DEMO_TENANT_ID,
    DEMO_USER_ID,
)

log = get_logger("seed")


def seed() -> None:
    # Tenant + identity + routing (non-RLS tables).
    with platform_session() as s:
        if s.get(Tenant, DEMO_TENANT_ID) is None:
            s.add(Tenant(id=DEMO_TENANT_ID, name="Demo Direct Tenant", type="DIRECT",
                         status="ACTIVE", settings={}))
        if s.get(User, DEMO_USER_ID) is None:
            s.add(User(id=DEMO_USER_ID, tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                       phone=DEMO_OWNER_PHONE, role=UserRole.OWNER.value, name="Ramesh Sharma",
                       locale=DEMO_LANGUAGE))
        existing_route = s.scalar(
            select(WaRoute).where(WaRoute.phone_number_id == DEMO_PHONE_NUMBER_ID)
        )
        if existing_route is None:
            s.add(WaRoute(phone_number_id=DEMO_PHONE_NUMBER_ID, tenant_id=DEMO_TENANT_ID,
                          account_id=DEMO_ACCOUNT_ID))
        # Admin/ops user on the DIRECT tenant.
        if s.get(User, DEMO_ADMIN_ID) is None:
            s.add(User(id=DEMO_ADMIN_ID, tenant_id=DEMO_TENANT_ID, account_id=None,
                       phone=DEMO_ADMIN_PHONE, role=UserRole.ADMIN.value, name="Asha (Ops)",
                       locale="en"))
        # A separate PARTNER tenant + user (agency console).
        if s.get(Tenant, DEMO_PARTNER_TENANT_ID) is None:
            s.add(Tenant(id=DEMO_PARTNER_TENANT_ID, name="Priya Digital (Partner)",
                         type="PARTNER", status="ACTIVE", settings={}))
        if s.get(User, DEMO_PARTNER_USER_ID) is None:
            s.add(User(id=DEMO_PARTNER_USER_ID, tenant_id=DEMO_PARTNER_TENANT_ID, account_id=None,
                       phone=DEMO_PARTNER_PHONE, role=UserRole.PARTNER.value, name="Priya",
                       locale="en"))
        # Shared (platform) WhatsApp templates — the only messages allowed outside the 24h
        # window. Seeded APPROVED so re-engagement/reports have something to send.
        for name, body in (
            ("re_engagement", "Namaste {{1}} 👋 You enquired with us recently — still "
                              "interested? Reply here and we'll help right away."),
            ("daily_summary", "Your Salmor update: {{1}} enquiries, {{2}} qualified today. "
                              "Spend so far: {{3}}."),
            ("welcome", "Namaste 👋 Thanks for reaching out. How can we help you today?"),
        ):
            if s.scalar(select(WaTemplate).where(WaTemplate.name == name)) is None:
                s.add(WaTemplate(tenant_id=None, account_id=None, name=name, language="hi",
                                 category="UTILITY", body=body, status="APPROVED"))

    # Account + profile + WhatsApp connection (RLS tables — under tenant context).
    with tenant_session(DEMO_TENANT_ID) as s:
        if s.get(Account, DEMO_ACCOUNT_ID) is None:
            s.add(Account(
                id=DEMO_ACCOUNT_ID, tenant_id=DEMO_TENANT_ID, business_name=DEMO_BUSINESS_NAME,
                category=DEMO_CATEGORY, phase=AccountPhase.LIVE.value,
                autopilot_level=AutopilotLevel.ASSISTED.value, default_language=DEMO_LANGUAGE,
                timezone="Asia/Kolkata", target_cpql_paise=int(Paise.from_rupees(200)),
                created_via="seed",
            ))
        exists_profile = s.scalar(
            select(BusinessProfile).where(BusinessProfile.account_id == DEMO_ACCOUNT_ID)
        )
        if exists_profile is None:
            s.add(BusinessProfile(
                tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                offer="NEET/JEE coaching with small batches and weekly tests",
                service_area_city=DEMO_CITY, service_radius_km=10,
                daily_budget_paise=int(Paise.from_rupees(1000)),
                monthly_cap_paise=int(Paise.from_rupees(15000)),
                raw_inputs={"seeded": True},
            ))
        exists_wa = s.scalar(
            select(WhatsAppConnection).where(WhatsAppConnection.account_id == DEMO_ACCOUNT_ID)
        )
        if exists_wa is None:
            s.add(WhatsAppConnection(
                tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                mode=WhatsAppMode.CLOUD_API.value, phone_number_id=DEMO_PHONE_NUMBER_ID,
                display_phone="+91 98765 00000", verified_name_status="APPROVED",
                quality_rating="GREEN",
            ))
        exists_meta = s.scalar(
            select(MetaConnection).where(MetaConnection.account_id == DEMO_ACCOUNT_ID)
        )
        if exists_meta is None:
            s.add(MetaConnection(
                tenant_id=DEMO_TENANT_ID, account_id=DEMO_ACCOUNT_ID,
                meta_business_id="100200300", ad_account_id="1234567890",
                page_id="9876543210", status="ACTIVE",
            ))

    log.info("seed_done", account=str(DEMO_ACCOUNT_ID))


def main() -> None:
    seed()
    print("✓ Seeded demo account:")
    print(f"  business : {DEMO_BUSINESS_NAME} ({DEMO_CATEGORY}, {DEMO_CITY})")
    print(f"  account  : {DEMO_ACCOUNT_ID}")
    print(f"  owner    : {DEMO_OWNER_PHONE}  (OTP dev code: 000000)")
    print(f"  wa route : phone_number_id {DEMO_PHONE_NUMBER_ID}")


if __name__ == "__main__":
    main()
