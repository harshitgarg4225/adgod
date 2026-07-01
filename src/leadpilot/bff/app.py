"""bff-api service — auth, leads inbox, dashboard, notifications (PRD §7.1, §9).

JWT auth, RFC-7807 errors with vernacular user_message, Idempotency-Key ready.
CORS open to the Next.js web app. Mobile-ready so an Expo app bolts on later.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from leadpilot.bff.routers import (
    admin,
    agents,
    auth,
    billing,
    bookings,
    leads,
    onboarding,
    partner,
)
from leadpilot.bff.routers import (
    settings as settings_router,
)
from leadpilot.common.config import settings
from leadpilot.common.errors import AppError, app_error_handler, unhandled_error_handler
from leadpilot.common.i18n import normalize_locale
from leadpilot.common.logging import configure_logging
from leadpilot.common.observability import init_observability, readiness
from leadpilot.common.security_headers import SecurityHeadersMiddleware

configure_logging()
init_observability("bff-api")

app = FastAPI(title="Salmor BFF", version="0.1.0")

# In production lock CORS to the known web origin(s) and do NOT pair "*" with credentials
# (the browser rejects that combo and it signals an over-broad policy).
_cors_origins = ["*"]
if settings.is_production:
    _configured = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
    _cors_origins = _configured or [settings.web_base_url]
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=not settings.is_production or _cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def locale_middleware(request: Request, call_next):
    request.state.locale = normalize_locale(request.headers.get("Accept-Language"))
    return await call_next(request)


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "bff-api", "env": settings.environment}


@app.get("/ready")
def ready() -> JSONResponse:
    r = readiness()
    return JSONResponse(r, status_code=200 if r["ready"] else 503)


API = "/api/v1"
app.include_router(auth.router, prefix=API)
app.include_router(onboarding.router, prefix=API)
app.include_router(leads.router, prefix=API)
app.include_router(bookings.router, prefix=API)
app.include_router(settings_router.router, prefix=API)
app.include_router(agents.router, prefix=API)
app.include_router(billing.router, prefix=API)
app.include_router(partner.router, prefix=API)
app.include_router(admin.router, prefix=API)
