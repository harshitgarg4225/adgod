"""Auth dependency: resolve the current principal from the Bearer JWT."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from leadpilot.common.auth import decode_token
from leadpilot.common.errors import AuthError, ForbiddenError

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
    request.state.locale = claims.get("locale", "en")
    return Principal(
        user_id=claims["sub"],
        tenant_id=claims["tid"],
        account_id=claims.get("aid"),
        role=claims.get("role", "OWNER"),
    )


def require_account_access(principal: Principal, account_id: str) -> None:
    """Owners may only touch their own account (RLS is the backstop)."""
    if principal.role in ("ADMIN", "OPS"):
        return
    if principal.account_id and principal.account_id != account_id:
        raise ForbiddenError("Not your account")
