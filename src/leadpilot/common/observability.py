"""Observability: best-effort Sentry init + a readiness probe (DB + Redis).

Sentry is optional — initialised only if SENTRY_DSN is set and the SDK is installed, so
it adds no hard dependency. `readiness()` backs the /ready endpoint for Railway health.
"""
from __future__ import annotations

from leadpilot.common.config import settings
from leadpilot.common.logging import get_logger

log = get_logger("observability")
_inited = False


def init_observability(service: str) -> None:
    global _inited
    if _inited:
        return
    _inited = True
    insecure = settings.insecure_secrets()
    if insecure and settings.is_production:
        # Fail-closed: dev-default secrets in production are a critical risk (forgeable
        # JWTs, decryptable Meta tokens). Refuse to boot rather than serve insecurely.
        log.error("INSECURE_SECRETS_IN_PRODUCTION", secrets=",".join(insecure))
        raise SystemExit(
            f"Refusing to start in production with dev-default secrets: {', '.join(insecure)}. "
            "Set strong JWT_SECRET and TOKEN_ENCRYPTION_KEY environment variables."
        )
    if settings.sentry_dsn:
        try:  # pragma: no cover - optional dependency
            import sentry_sdk

            sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment,
                            traces_sample_rate=0.1, server_name=service)
            log.info("sentry_initialised", service=service)
        except Exception as exc:  # noqa: BLE001
            log.warning("sentry_init_failed", error=str(exc))


def _redis_ok() -> bool:
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        return bool(client.ping())
    except Exception:
        return False


def readiness() -> dict:
    from leadpilot.core.db import healthcheck

    db_ok = healthcheck()
    redis_ok = _redis_ok()
    return {"ready": db_ok and redis_ok, "db": db_ok, "redis": redis_ok}
