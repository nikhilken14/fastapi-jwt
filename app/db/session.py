"""
Database engine + session factory.

Using a real database (via SQLAlchemy) instead of an in-memory Python
list/dict is what makes this "production-like" - data survives restarts,
supports concurrent access safely, and the swap from SQLite to Postgres
in production is a one-line change to DATABASE_URL, nothing else.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.user import Base

settings = get_settings()

# `echo=False` keeps SQL statements out of logs by default; flip to True
# locally if you need to debug generated queries.
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# `expire_on_commit=False` lets us keep using ORM objects returned from a
# session after it's closed (e.g. reading fields in a route handler) -
# convenient in a small service like this one.
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields one DB session per request.

    Using `Depends(get_db)` means every request gets its own session
    that's guaranteed to be closed afterward (even if the request
    raises an exception), rather than routes managing sessions manually.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables if they don't exist yet.

    Called once at startup (see app/main.py lifespan). A real production
    system would use Alembic migrations instead of `create_all` so
    schema changes are versioned and reviewable - this is the
    "good enough for a small service / demo" version of that step.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)