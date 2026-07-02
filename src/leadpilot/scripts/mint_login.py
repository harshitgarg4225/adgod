"""Operator escape hatch: mint a one-time login code for a phone, bypassing SMS.

Onboarding a client at their shop must never depend on MSG91 delivery. This inserts a
short-lived OTP row directly (same salted hash the verify endpoint checks), prints the
code, and the client types it into the normal login screen. Run it on the server
(`railway run …`) — it needs DB access, and the code is shown only to whoever ran it.

Usage:
  python -m leadpilot.scripts.mint_login --phone 9812345678 [--ttl-min 10]
"""
from __future__ import annotations

import argparse
import secrets
from datetime import UTC, datetime, timedelta

from leadpilot.common.auth import hash_otp
from leadpilot.common.phone import normalize_phone
from leadpilot.core.db import platform_session
from leadpilot.core.models import AuthOtp


def mint_login(phone: str, ttl_min: int = 10) -> tuple[str, str]:
    phone = normalize_phone(phone)
    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(16)
    with platform_session() as s:
        s.add(AuthOtp(phone=phone, code_hash=hash_otp(code, salt), salt=salt,
                      expires_at=datetime.now(UTC) + timedelta(minutes=ttl_min)))
    return phone, code


def main() -> None:
    p = argparse.ArgumentParser(description="Mint a login OTP without SMS (operator use)")
    p.add_argument("--phone", required=True)
    p.add_argument("--ttl-min", type=int, default=10)
    a = p.parse_args()
    phone, code = mint_login(a.phone, a.ttl_min)
    print(f"✓ Login code for {phone}: {code}  (valid {a.ttl_min} min)")
    print("  Enter it on the normal login screen after tapping 'Get code'... any pending")
    print("  SMS code is superseded — this one is the newest, so verify uses it.")


if __name__ == "__main__":
    main()
