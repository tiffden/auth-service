from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.courses import router as courses_router
from app.api.credentials import router as credentials_router
from app.api.health import router as health_router
from app.api.login import router as login_router
from app.api.logout import router as logout_router
from app.api.metrics_endpoint import router as metrics_router
from app.api.oauth import router as oauth_router
from app.api.orgs import router as orgs_router
from app.api.profile import router as profile_router
from app.api.progress import router as progress_router
from app.api.register import router as register_router
from app.api.resource import router as resource_router
from app.api.users import router as users_router
from app.core.config import SETTINGS
from app.core.logging import setup_logging
from app.db.engine import lifespan_db
from app.db.redis import lifespan_redis
from app.middleware.metrics import MetricsMiddleware
from app.middleware.request_context import RequestContextMiddleware

# Configure logging before anything else runs.
setup_logging(SETTINGS.log_level, json_format=SETTINGS.log_json)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # Each backing service (DB, Redis) has its own startup/shutdown
    # lifecycle.  Nesting ensures teardown in reverse order (LIFO)
    # even if one fails — the same principle as nested try/finally.
    async with lifespan_db():
        async with lifespan_redis():
            yield


# only app setup + router registration

app = FastAPI(
    title="auth-service",
    lifespan=lifespan,
    docs_url="/docs" if SETTINGS.is_dev else None,
    redoc_url="/redoc" if SETTINGS.is_dev else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware execution order: last-added runs first (outermost layer).
# RequestContext (outermost) → Metrics → CORS → route handler
# This ensures every request gets a request ID before metrics are recorded.
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestContextMiddleware)

app.include_router(metrics_router)
app.include_router(admin_router)
app.include_router(courses_router)
app.include_router(credentials_router)
app.include_router(health_router)
app.include_router(login_router)
app.include_router(logout_router)
app.include_router(oauth_router)
app.include_router(orgs_router)
app.include_router(profile_router)
app.include_router(progress_router)
app.include_router(register_router)
app.include_router(resource_router)
app.include_router(users_router)

logger.info(
    "auth-service started  env=%s log_level=%s port=%d docs=%s",
    SETTINGS.app_env,
    SETTINGS.log_level,
    SETTINGS.port,
    "on" if SETTINGS.is_dev else "off",
)
