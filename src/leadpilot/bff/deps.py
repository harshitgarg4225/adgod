"""Auth dependency: resolve the current principal from the Bearer JWT."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from leadpilot.common.auth import decode_token
from leadpilot.common.errors import AuthError, ForbiddenError
from leadpilot.core.db import platform_session
from leadpilot.core.models import User

bearer = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class Principal:
    user_id: str
    tenant_id: str
    account_id: str | None
    role: str


def current_principal(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Principal:
    if creds is None or not creds.credentials:
        raise AuthError("Missing bearer token")
    try:
        claims = decode_token(creds.credentials)
    except Exception as exc:  # noqa: BLE001
        raise AuthError("Invalid or expired token") from exc
    if claims.get("type") != "access":
        raise AuthError("Wrong token type")
    # Re-bind the token to the live user row every request: this revokes tokens after
    # logout (token_version bump) or account deletion, and stops a forged/replayed token
    # from asserting a tenant the user isn't actually in.
    with platform_session() as s:
        user = s.get(User, claims["sub"])
    if user is None or user.deleted_at is not None:
        raise AuthError("Account no longer active")
    if str(user.tenant_id) != claims.get("tid"):
        raise AuthError("Token tenant mismatch")
    if int(claims.get("tv", 0)) != int(user.token_version):
        raise AuthError("Session expired, please log in again")
    request.state.locale = user.locale or "en"
    return Principal(
        user_id=claims["sub"],
        tenant_id=claims["tid"],
        account_id=claims.get("aid"),
        role=claims.get("role", "OWNER"),
    )


def require_account_access(principal: Principal, account_id: str) -> None:
    """Owners may only touch their own account (RLS is the backstop).

    PARTNER/ADMIN/OPS act tenant-wide (RLS confines them to their tenant). For an OWNER we
    require an EXACT account match — a null `account_id` is treated as no-access rather than
    all-access, closing an IDOR where an owner row with no bound account could reach any
    account in the tenant.
    """
    if principal.role in ("ADMIN", "OPS", "PARTNER"):
        return
    if principal.account_id is None or principal.account_id != account_id:
        raise ForbiddenError("Not your account")


def require_role(principal: Principal, allowed: set[str]) -> None:
    if principal.role not in allowed:
        raise ForbiddenError("Insufficient role")
