from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.users import router as users_router
from app.core.config import SETTINGS
from app.core.logging import setup_logging

# Configure logging before anything else runs.
setup_logging(SETTINGS.log_level)

logger = logging.getLogger(__name__)

# only app setup + router registration

app = FastAPI(
    title="auth-service",
    docs_url="/docs" if not SETTINGS.is_prod else None,
    redoc_url="/redoc" if not SETTINGS.is_prod else None,
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)

logger.info(
    "auth-service started  env=%s log_level=%s docs=%s",
    SETTINGS.app_env,
    SETTINGS.log_level,
    "on" if not SETTINGS.is_prod else "off",
)
