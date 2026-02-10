from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

AppEnv = Literal["dev", "test", "prod"]
LogLevel = Literal["debug", "info", "warning", "error"]


def _getenv(name: str, default: str) -> str:
    # Centralize env access so it’s easy to extend later (type casting, required vars)
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    app_env: AppEnv
    log_level: LogLevel

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


def load_settings() -> Settings:
    app_env_raw = _getenv("APP_ENV", "dev").lower()
    log_level_raw = _getenv("LOG_LEVEL", "info").lower()

    if app_env_raw not in ("dev", "test", "prod"):
        raise ValueError(f"APP_ENV must be dev|test|prod (got {app_env_raw!r})")

    if log_level_raw not in ("debug", "info", "warning", "error"):
        raise ValueError(
            f"LOG_LEVEL must be debug|info|warning|error (got {log_level_raw!r})"
        )

    return Settings(app_env=app_env_raw, log_level=log_level_raw)  # type: ignore[arg-type]


# Optional: module-level singleton so imports are cheap
SETTINGS = load_settings()
