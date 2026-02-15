"""Alembic environment configuration.

Reads DATABASE_URL from app.core.config (same source as the running app)
and imports the SQLAlchemy metadata for autogenerate support.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import SETTINGS
from app.db.engine import Base

# Alembic Config object — provides access to alembic.ini values.
config = context.config

# Override sqlalchemy.url from our app config (not the .ini placeholder).
if SETTINGS.database_url:
    # asyncpg URLs need to be converted to psycopg2-style for Alembic
    # (Alembic runs synchronous migrations).
    sync_url = SETTINGS.database_url.replace("postgresql+asyncpg", "postgresql")
    config.set_main_option("sqlalchemy.url", sync_url)

# Set up Python logging from the .ini file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy MetaData for autogenerate support.
# Import table module so Base.metadata sees all table definitions.
import app.db.tables  # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL without a live DB)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connected to a live DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
