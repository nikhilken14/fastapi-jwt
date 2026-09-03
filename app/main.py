"""
Application entry point: wires together config, logging, the database,
routers, and error handling into one FastAPI app.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import auth, users
from app.core.config import get_settings
from app.core.exceptions import AppError, app_error_handler, unhandled_error_handler
from app.core.logging import configure_logging
from app.db.session import init_db

settings = get_settings()
configure_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hook: create DB tables before the app starts serving traffic."""
    await init_db()
    yield


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

# Every AppError subclass (see app/core/exceptions.py) is handled the
# same way; genuinely unexpected exceptions get the generic 500 handler.
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

app.include_router(auth.router)
app.include_router(users.router)


@app.get("/health", tags=["ops"])
def health_check():
    """Liveness/readiness probe for load balancers and orchestrators."""
    return {"status": "ok", "service": settings.APP_NAME}