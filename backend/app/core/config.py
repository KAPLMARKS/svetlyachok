"""Конфигурация приложения через pydantic-settings.

Все настройки загружаются из .env-файла или переменных окружения.
SecretStr-поля маскируются в repr/log для предотвращения утечек.

Использование:
    from app.core.config import get_settings
    settings = get_settings()  # кешируется через lru_cache
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


Environment = Literal["development", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
LogFormat = Literal["json", "console"]


class Settings(BaseSettings):
    """Главная конфигурация приложения.

    Поля без значений по умолчанию (database_url, jwt_secret) обязательны.
    Их отсутствие приведёт к ValidationError при старте — fail fast.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---

    app_name: str = Field(
        default="svetlyachok-backend",
        description="Имя приложения. Используется в FastAPI title и логах.",
    )

    environment: Environment = Field(
        default="development",
        description="Окружение запуска. Влияет на формат логов и debug-флаги.",
    )

    # --- Logging ---

    log_level: LogLevel = Field(
        default="DEBUG",
        description="Уровень логирования. В production обычно INFO.",
    )

    log_format: LogFormat = Field(
        default="json",
        description="Формат логов. 'console' удобнее в dev, 'json' — для production.",
    )

    # --- Database ---

    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL DSN. Пример: postgresql+asyncpg://user:pass@host:5432/svetlyachok",
    )

    # --- JWT / Security ---

    jwt_secret: SecretStr = Field(
        ...,
        description="Секрет для подписи JWT. Минимум 32 символа.",
    )

    jwt_algorithm: str = Field(
        default="HS256",
        description="Алгоритм подписи JWT.",
    )

    jwt_access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Время жизни access-токена (минуты, 1..1440).",
    )

    jwt_refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Время жизни refresh-токена (дни, 1..90).",
    )

    # --- CORS ---

    cors_origins: list[AnyHttpUrl] = Field(
        default_factory=list,
        description="Список разрешённых origin для CORS. Пустой = CORS отключён.",
    )

    # --- Rate limiting ---

    auth_login_rate_limit: str = Field(
        default="5/minute",
        description=(
            "Лимит на /api/v1/auth/login. Формат slowapi: '<count>/<period>'. "
            "Защита от брутфорса; снижать только в exceptional cases."
        ),
    )

    auth_refresh_rate_limit: str = Field(
        default="10/minute",
        description="Лимит на /api/v1/auth/refresh. Формат slowapi.",
    )

    # --- Validators ---

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_be_long(cls, v: SecretStr) -> SecretStr:
        """JWT-секрет короче 32 символов небезопасен."""
        secret_value = v.get_secret_value()
        if len(secret_value) < 32:
            raise ValueError(
                "jwt_secret must be at least 32 characters long for HS256 security"
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Загружает Settings и кеширует результат.

    Кеширование на module-level singleton для производительности
    (валидация и парсинг .env происходят один раз).

    Логирует факт загрузки на DEBUG. SecretStr-поля автоматически маскируются
    в model_dump_json и repr.
    """
    settings = Settings()  # type: ignore[call-arg]  # обязательные поля приходят из .env
    logger.debug(
        "[Settings.load] loaded environment=%s log_level=%s log_format=%s",
        settings.environment,
        settings.log_level,
        settings.log_format,
    )
    return settings
