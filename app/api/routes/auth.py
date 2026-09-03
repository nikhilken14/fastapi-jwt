"""
Public authentication endpoints: register, log in, refresh a token.

Notice these handlers are thin - they validate input (via Pydantic
schemas), delegate to app/core/security.py for anything
security-sensitive, and talk to the DB directly since the logic here is
simple enough not to warrant a separate service layer. In a larger
service you'd likely extract a `UserService` class instead.
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import RefreshRequest, TokenPair, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user account.

    Raises:
        UserAlreadyExistsError (409): if the email is already registered.
    """
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise UserAlreadyExistsError(f"Email '{payload.email}' is already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password), role="user")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("user registered", extra={"user_id": user.id})
    return user


@router.post("/token", response_model=TokenPair)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """OAuth2 'password' grant: exchange email+password for a token pair.

    Returns both an access token (short-lived, used on every request)
    and a refresh token (long-lived, used only to get new access tokens).

    Raises:
        InvalidCredentialsError (401): wrong email or password.
    """
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.password_hash):
        raise InvalidCredentialsError("Incorrect email or password")

    logger.info("user logged in", extra={"user_id": user.id})
    return TokenPair(
        access_token=create_access_token(user.email, user.role),
        refresh_token=create_refresh_token(user.email, user.role),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest):
    """Exchange a valid, unexpired refresh token for a brand new token pair.

    This lets a client stay "logged in" for a long time (REFRESH_TOKEN_EXPIRE_DAYS)
    without ever storing the original password, while access tokens
    themselves stay short-lived (limiting the damage if one leaks).

    Raises:
        InvalidTokenError (401): if the refresh token is invalid, expired,
            or is actually an access token.
    """
    claims = decode_token(payload.refresh_token, expected_type=TokenType.REFRESH)
    email, role = claims["sub"], claims["role"]

    return TokenPair(
        access_token=create_access_token(email, role),
        refresh_token=create_refresh_token(email, role),
    )