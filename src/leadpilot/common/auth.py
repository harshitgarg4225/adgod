"""JWT issue/verify for the owner/partner/admin surfaces + the OTP hash."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from leadpilot.common.config import settings

ALGO = "HS256"


def hash_otp(code: str, salt: str) -> str:
    """Salted OTP hash (per-row random salt defeats precomputation; the JWT secret is an
    extra pepper). Shared by the auth router and the operator mint_login script."""
    return hashlib.sha256(f"{salt}:{settings.jwt_secret}:{code}".encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def issue_access_token(
    *, user_id: str, tenant_id: str, account_id: str | None, role: str, token_version: int = 0
) -> str:
    payload = {
        "sub": user_id,
        "tid": tenant_id,
        "aid": account_id,
        "role": role,
        "tv": token_version,  # must match users.token_version or the token is revoked
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.jwt_access_ttl_min),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)


def issue_refresh_token(*, user_id: str, tenant_id: str) -> str:
    payload = {
        "sub": user_id,
        "tid": tenant_id,
        "type": "refresh",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.jwt_refresh_ttl_min),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
