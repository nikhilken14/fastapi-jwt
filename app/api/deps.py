"""
Shared FastAPI dependencies: "who is calling, and are they allowed to do this?"

Route handlers depend on `get_current_user` or `require_admin` instead of
each re-implementing token parsing - this is where authentication and
authorization actually happen, once, for the whole API.
"""

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidTokenError, PermissionDeniedError
from app.core.security import TokenType, decode_token
from app.db.session import get_db
from app.models.user import User

# `tokenUrl` only affects the auto-generated Swagger UI "Authorize" flow.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the calling user from their access token.

    This is the AUTHENTICATION dependency: it proves the token is
    genuine, unexpired, and of the correct type, then loads the
    corresponding user row so handlers have real user data to work with.

    Raises:
        InvalidTokenError: bad/expired/wrong-type token, or the user
            referenced by the token no longer exists.
    """
    payload = decode_token(token, expected_type=TokenType.ACCESS)
    email = payload.get("sub")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise InvalidTokenError("User for this token no longer exists")

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """AUTHORIZATION dependency: builds on `get_current_user`, then checks role.

    Any route depending on this is guaranteed to already have a verified,
    still-existing user AND that user has the "admin" role.
    """
    if user.role != "admin":
        raise PermissionDeniedError("This action requires admin privileges")
    return user