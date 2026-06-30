"""Symmetric encryption for secrets at rest (Meta system-user tokens).

Fernet (AES-128-CBC + HMAC) keyed deterministically from TOKEN_ENCRYPTION_KEY so the
same key decrypts across services. Tokens are NEVER logged (see logging redaction).
In production, supply a strong 32+ byte TOKEN_ENCRYPTION_KEY via a secret manager.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from leadpilot.common.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.token_encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    return _fernet().decrypt(token.encode()).decode()
