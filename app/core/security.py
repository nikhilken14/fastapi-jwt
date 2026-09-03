"""
Password hashing and JWT creation/verification.

Kept separate from app/api and app/services because this is pure,
security-critical logic that should have no knowledge of HTTP, the
database, or FastAPI - easy to unit test in isolation, and there is
exactly one place in the codebase that knows how tokens are signed.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError

settings = get_settings()


class TokenType(str, Enum):
    """Distinguishes access tokens from refresh tokens.

    Encoding this INSIDE the JWT (as the `type` claim) stops a client
    from using a long-lived refresh token to call normal protected
    endpoints, or a short-lived access token to mint a new one -
    each token type is only accepted where it's supposed to be used.
    """
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for storage. Never store plaintext passwords."""
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())


def _create_token(subject: str, role: str, token_type: TokenType, expires_delta: timedelta) -> str:
    """Shared internal helper for building any JWT this service issues."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,          # the user's identity (here, their email)
        "role": role,
        "type": token_type.value,
        "iat": now,              # issued-at, useful for auditing/debugging
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    """Create a short-lived access token, sent with every API request."""
    return _create_token(
        subject, role, TokenType.ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str, role: str) -> str:
    """Create a long-lived refresh token, used only to obtain new access tokens."""
    return _create_token(
        subject, role, TokenType.REFRESH,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: TokenType) -> dict:
    """Verify a JWT's signature/expiry and check it's the expected type.

    Args:
        token: The raw JWT string from the client.
        expected_type: Which kind of token this endpoint requires
            (e.g. the refresh endpoint should reject an access token).

    Returns:
        The decoded claims (sub, role, type, iat, exp).

    Raises:
        InvalidTokenError: If the signature is bad, it's expired, or its
            `type` claim doesn't match `expected_type`.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("Token has expired")
    except jwt.InvalidTokenError:
        raise InvalidTokenError("Token is invalid")

    if payload.get("type") != expected_type.value:
        raise InvalidTokenError(f"Expected a {expected_type.value} token")

    return payload