"""Create the founder's ADMIN user — the back office (admin console, impersonation,
anomaly queue, feature flags) is unreachable without one, and seeding demo data into a
production DB just to get an admin is not an option.

Idempotent per phone: re-running updates the role instead of failing.

Usage:
  python -m leadpilot.scripts.create_admin --phone 9800000000 --name "Founder" [--role OPS]
"""
from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from leadpilot.common.phone import normalize_phone
from leadpilot.core.db import platform_session
from leadpilot.core.enums import TenantType, UserRole
from leadpilot.core.models import Tenant, User


def create_admin(phone: str, name: str | None, role: str = "ADMIN") -> dict:
    phone = normalize_phone(phone)
    with platform_session() as s:
        user = s.scalar(select(User).where(User.phone == phone))
        if user is not None:
            user.role = role
            user.deleted_at = None
            return {"user_id": str(user.id), "phone": phone, "role": role, "created": False}
        tenant_id = uuid.uuid4()
        s.add(Tenant(id=tenant_id, name="Salmor Ops", type=TenantType.DIRECT.value,
                     status="ACTIVE", settings={"platform": True}))
        user = User(id=uuid.uuid4(), tenant_id=tenant_id, account_id=None, phone=phone,
                    role=role, name=name, locale="en", consent_at=datetime.now(UTC))
        s.add(user)
        return {"user_id": str(user.id), "phone": phone, "role": role, "created": True}


def main() -> None:
    p = argparse.ArgumentParser(description="Create/promote a Salmor ADMIN/OPS user")
    p.add_argument("--phone", required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--role", default=UserRole.ADMIN.value,
                   choices=[UserRole.ADMIN.value, UserRole.OPS.value])
    a = p.parse_args()
    out = create_admin(a.phone, a.name, a.role)
    verb = "created" if out["created"] else "updated"
    print(f"✓ {out['role']} user {verb}: {out['phone']} (user_id {out['user_id']})")
    print("  Log in with this phone via OTP (or mint one: python -m "
          "leadpilot.scripts.mint_login --phone ...)")
    print("  Back office: open /admin after logging in — fleet view, daily digest,")
    print("  anomaly queue, impersonation.")


if __name__ == "__main__":
    main()
