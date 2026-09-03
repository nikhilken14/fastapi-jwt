"""
Pydantic models defining the public API contract for auth endpoints.

These are what clients actually see in requests/responses - notice
`UserOut` deliberately has no `password_hash` field, so there is no way
for a hashed password to accidentally leak into an API response even if
a route handler is careless about what it returns.
"""

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Request body for POST /auth/register."""
    email: EmailStr
    password: str = Field(min_length=8, description="Minimum 8 characters")


class UserOut(BaseModel):
    """Public-facing representation of a user - never includes the password hash."""
    id: int
    email: EmailStr
    role: str

    model_config = {"from_attributes": True}  # allows `UserOut.model_validate(orm_user)`


class TokenPair(BaseModel):
    """Response body returned on successful login or token refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request body for POST /auth/refresh."""
    refresh_token: str