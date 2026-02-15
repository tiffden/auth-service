from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.courses import router as courses_router
from app.api.credentials import router as credentials_router
from app.api.health import router as health_router
from app.api.login import router as login_router
from app.api.oauth import router as oauth_router
from app.api.progress import router as progress_router
from app.api.resource import router as resource_router
from app.api.users import router as users_router
from app.core.config import SETTINGS
from app.core.logging import setup_logging
from app.db.engine import lifespan_db

# Configure logging before anything else runs.
setup_logging(SETTINGS.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    async with lifespan_db():
        yield


# only app setup + router registration

app = FastAPI(
    title="auth-service",
    lifespan=lifespan,
    docs_url="/docs" if SETTINGS.is_dev else None,
    redoc_url="/redoc" if SETTINGS.is_dev else None,
)

app.include_router(admin_router)
app.include_router(courses_router)
app.include_router(credentials_router)
app.include_router(health_router)
app.include_router(login_router)
app.include_router(oauth_router)
app.include_router(progress_router)
app.include_router(resource_router)
app.include_router(users_router)

logger.info(
    "auth-service started  env=%s log_level=%s port=%d docs=%s",
    SETTINGS.app_env,
    SETTINGS.log_level,
    SETTINGS.port,
    "on" if SETTINGS.is_dev else "off",
)
