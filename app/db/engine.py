"""Async SQLAlchemy engine and session factory.

When DATABASE_URL is configured, provides:
- async engine for PostgreSQL via asyncpg
- async session factory for request-scoped sessions
- FastAPI lifespan hook for startup/shutdown

When DATABASE_URL is None (no database configured), all exports are None
and the app falls back to in-memory repositories.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import SETTINGS

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all table models."""


# --- Engine and session factory (None when no DATABASE_URL) ---

if SETTINGS.database_url:
    engine = create_async_engine(
        SETTINGS.database_url,
        echo=SETTINGS.is_dev,  # log SQL in dev only
        pool_size=5,
        max_overflow=10,
    )
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
else:
    engine = None
    async_session_factory = None


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a request-scoped async session.

    Commits on success, rolls back on exception.
    """
    if async_session_factory is None:
        raise RuntimeError(
            "DATABASE_URL is not configured — cannot create database session"
        )
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def lifespan_db():
    """Startup/shutdown hook for the database engine.

    Call from FastAPI's lifespan context manager.
    """
    if engine is None:
        logger.info("No DATABASE_URL configured — using in-memory repositories")
        yield
        return

    logger.info("Database engine created: %s", engine.url)
    yield
    await engine.dispose()
    logger.info("Database engine disposed")
