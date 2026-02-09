from __future__ import annotations

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.users import router as users_router
from app.core.config import SETTINGS

app = FastAPI(
    title="auth-service",
    docs_url="/docs" if not SETTINGS.is_prod else None,
    redoc_url="/redoc" if not SETTINGS.is_prod else None,
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
