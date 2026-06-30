"""bff-api service — auth, leads inbox, dashboard, notifications (PRD §7.1, §9).

JWT auth, RFC-7807 errors with vernacular user_message, Idempotency-Key ready.
CORS open to the Next.js web app. Mobile-ready so an Expo app bolts on later.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from leadpilot.bff.routers import agents, auth, billing, leads, onboarding
from leadpilot.common.config import settings
from leadpilot.common.errors import AppError, app_error_handler, unhandled_error_handler
from leadpilot.common.i18n import normalize_locale
from leadpilot.common.logging import configure_logging

configure_logging()

app = FastAPI(title="LeadPilot BFF", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [settings.app_base_url],
    allow_credentials=True,
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


API = "/api/v1"
app.include_router(auth.router, prefix=API)
app.include_router(onboarding.router, prefix=API)
app.include_router(leads.router, prefix=API)
app.include_router(agents.router, prefix=API)
app.include_router(billing.router, prefix=API)
