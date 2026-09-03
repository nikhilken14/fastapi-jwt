"""
SQLAlchemy ORM model for the `users` table.

This is the persistence-layer representation of a user - separate from
`app/schemas/auth.py`, which defines what user data looks like over the
API. Keeping these separate means you can change the DB schema without
automatically changing (or breaking) the public API contract, and vice versa.
"""

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models in this service."""
    pass


class User(Base):
    """A registered user.

    Columns:
        id: Auto-incrementing primary key.
        email: Unique login identifier.
        password_hash: bcrypt hash - the plaintext password is never stored.
        role: "user" or "admin" - drives authorization checks in the API layer.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")