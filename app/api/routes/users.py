"""
Protected endpoints demonstrating the two dependency levels defined in
app/api/deps.py: authentication-only vs. authentication + authorization.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_current_user(current_user: User = Depends(get_current_user)):
    """Return the profile of whoever the access token belongs to.

    Any authenticated user (any role) can call this - it only checks
    "is this a valid token", not "what role does this user have."
    """
    return current_user


@router.get("/admin/all", response_model=list[UserOut])
async def list_all_users(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Admin-only endpoint: returns every registered user.

    Non-admin users get a 403 here (not a 401) - `require_admin` already
    confirms they're logged in, then additionally checks their role.
    """
    result = await db.execute(select(User))
    return result.scalars().all()