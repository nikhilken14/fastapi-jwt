"""
Domain-specific exceptions + a single place that turns them into HTTP responses.

Production APIs distinguish between:
    - Expected, "business logic" failures (wrong password, duplicate
      email, expired token) - these should return clean, predictable
      error JSON with an appropriate status code.
    - Genuine bugs/crashes - these should return a generic 500 and get
      logged with a full stack trace, never leak internals to the client.

Raising typed exceptions like `InvalidCredentialsError` (instead of
`HTTPException` directly, scattered through route handlers) keeps the
business logic (app/services, app/api) decoupled from HTTP concerns -
the exception handlers below are the only place that knows about status
codes.
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for all expected application errors.

    Attributes:
        message: Human-readable detail returned to the client.
        status_code: HTTP status code to respond with.
    """

    status_code = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class InvalidCredentialsError(AppError):
    """Raised when a login attempt has a wrong username/password."""
    status_code = 401


class InvalidTokenError(AppError):
    """Raised when a JWT is missing, malformed, expired, or has been revoked."""
    status_code = 401


class PermissionDeniedError(AppError):
    """Raised when an authenticated user lacks the role/permission required."""
    status_code = 403


class UserAlreadyExistsError(AppError):
    """Raised when registering with an email that's already taken."""
    status_code = 409


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert any `AppError` subclass into a clean JSON error response.

    Registered on the FastAPI app in app/main.py. Because every expected
    error type inherits from `AppError`, this ONE handler covers all of
    them - new error types don't require new handlers, just a new subclass.
    """
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for anything that isn't an `AppError` - i.e. real bugs.

    Logs the full exception (with stack trace) for debugging, but returns
    a generic message to the client so internals are never leaked.
    """
    logger.exception("Unhandled exception while processing request", exc_info=exc)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})