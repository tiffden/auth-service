from __future__ import annotations

import pytest

from app.core.config import Settings, load_settings

# ---- valid values ----


def test_load_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    settings = load_settings()
    assert settings.app_env == "dev"
    assert settings.log_level == "info"


def test_load_settings_respects_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("LOG_LEVEL", "error")
    settings = load_settings()
    assert settings.app_env == "prod"
    assert settings.log_level == "error"


def test_load_settings_normalizes_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "PROD")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = load_settings()
    assert settings.app_env == "prod"
    assert settings.log_level == "debug"


def test_load_settings_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "  test  ")
    monkeypatch.setenv("LOG_LEVEL", "  warning  ")
    settings = load_settings()
    assert settings.app_env == "test"
    assert settings.log_level == "warning"


# ---- invalid APP_ENV ----


def test_load_settings_rejects_invalid_app_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("LOG_LEVEL", "info")
    with pytest.raises(ValueError, match="APP_ENV must be dev|test|prod"):
        load_settings()


def test_load_settings_rejects_empty_app_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "")
    with pytest.raises(ValueError, match="APP_ENV must be dev|test|prod"):
        load_settings()


# ---- invalid LOG_LEVEL ----


def test_load_settings_rejects_invalid_log_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("LOG_LEVEL", "verbose")
    with pytest.raises(ValueError, match="LOG_LEVEL must be debug|info|warning|error"):
        load_settings()


def test_load_settings_rejects_empty_log_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "")
    with pytest.raises(ValueError, match="LOG_LEVEL must be debug|info|warning|error"):
        load_settings()


# ---- Settings properties ----


def test_settings_is_dev() -> None:
    s = Settings(app_env="dev", log_level="info")  # type: ignore[arg-type]
    assert s.is_dev is True
    assert s.is_test is False
    assert s.is_prod is False


def test_settings_is_test() -> None:
    s = Settings(app_env="test", log_level="info")  # type: ignore[arg-type]
    assert s.is_dev is False
    assert s.is_test is True
    assert s.is_prod is False


def test_settings_is_prod() -> None:
    s = Settings(app_env="prod", log_level="info")  # type: ignore[arg-type]
    assert s.is_dev is False
    assert s.is_test is False
    assert s.is_prod is True


def test_settings_is_frozen() -> None:
    s = Settings(app_env="dev", log_level="info")  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        s.app_env = "prod"  # type: ignore[misc]
