"""Unit-тесты загрузки настроек."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

pytestmark = pytest.mark.unit


def test_settings_load_with_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings успешно грузятся при наличии всех обязательных переменных."""
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    settings = get_settings()

    assert isinstance(settings, Settings)
    assert settings.environment == "development"
    assert settings.log_level == "DEBUG"
    assert str(settings.database_url).startswith("postgresql+asyncpg://")


def test_settings_missing_database_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Отсутствие DATABASE_URL вызывает ValidationError при инициализации."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(PydanticValidationError) as exc_info:
        Settings()  # type: ignore[call-arg]

    assert "database_url" in str(exc_info.value).lower()


def test_settings_short_jwt_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT secret короче 32 символов недопустим."""
    monkeypatch.setenv("JWT_SECRET", "too_short")

    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(PydanticValidationError) as exc_info:
        Settings()  # type: ignore[call-arg]

    assert "32 characters" in str(exc_info.value)


def test_jwt_secret_is_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    """SecretStr должен маскировать значение в repr и model_dump."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    repr_str = repr(settings)
    assert "test_secret" not in repr_str
    assert "**********" in repr_str or "SecretStr" in repr_str

    dumped = settings.model_dump_json()
    # SecretStr в model_dump сериализуется в "**********"
    assert "test_secret_at_least_32_chars" not in dumped
