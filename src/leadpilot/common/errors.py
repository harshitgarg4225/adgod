"""RFC-7807 problem+json errors with a vernacular `user_message`.

Every API error the owner can hit carries a localized, plain-language message.
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from leadpilot.common.i18n import t


class AppError(Exception):
    """Base application error → RFC-7807 problem+json."""

    status_code: int = 400
    error_type: str = "about:blank"
    title: str = "Bad Request"
    # i18n key resolved against the request locale for the human-facing message.
    user_message_key: str = "error.generic"

    def __init__(
        self,
        detail: str | None = None,
        *,
        user_message_key: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.detail = detail or self.title
        if user_message_key:
            self.user_message_key = user_message_key
        self.extra = extra or {}
        super().__init__(self.detail)

    def to_problem(self, locale: str, instance: str) -> dict[str, Any]:
        problem = {
            "type": self.error_type,
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
            "instance": instance,
            "user_message": t(self.user_message_key, locale),
        }
        problem.update(self.extra)
        return problem


class ValidationError(AppError):
    status_code = 422
    error_type = "https://leadpilot.app/errors/validation"
    title = "Validation Error"
    user_message_key = "error.validation"


class AuthError(AppError):
    status_code = 401
    error_type = "https://leadpilot.app/errors/unauthorized"
    title = "Unauthorized"
    user_message_key = "error.unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    error_type = "https://leadpilot.app/errors/forbidden"
    title = "Forbidden"
    user_message_key = "error.forbidden"


class NotFoundError(AppError):
    status_code = 404
    error_type = "https://leadpilot.app/errors/not-found"
    title = "Not Found"
    user_message_key = "error.not_found"


class ConflictError(AppError):
    status_code = 409
    error_type = "https://leadpilot.app/errors/conflict"
    title = "Conflict"
    user_message_key = "error.conflict"


class WebhookSignatureError(AppError):
    status_code = 403
    error_type = "https://leadpilot.app/errors/webhook-signature"
    title = "Invalid Webhook Signature"
    user_message_key = "error.forbidden"


class GuardrailBlocked(AppError):
    """Raised when the Guardrail Engine blocks an action."""

    status_code = 409
    error_type = "https://leadpilot.app/errors/guardrail"
    title = "Action Blocked by Guardrail"
    user_message_key = "error.generic"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    locale = getattr(request.state, "locale", "en")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_problem(locale, str(request.url.path)),
        media_type="application/problem+json",
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    locale = getattr(request.state, "locale", "en")
    problem = {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "An unexpected error occurred.",
        "instance": str(request.url.path),
        "user_message": t("error.generic", locale),
    }
    return JSONResponse(status_code=500, content=problem, media_type="application/problem+json")
