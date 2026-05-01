"""Корневой pytest conftest: общие fixtures для всех тестов.

Принципы:
- Каждый тест получает изолированную FastAPI app через `app` fixture.
- HTTP-клиент (`httpx.AsyncClient`) для интеграционных тестов API.
- Тесты используют фиктивные секреты из .env.test (через monkeypatch.setenv).
- Settings cache (lru_cache) очищается между тестами.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Автоматически выставляет минимально необходимые env-переменные.

    Применяется ко ВСЕМ тестам. Конкретный тест может переопределить
    значения через свой monkeypatch.setenv.
    """
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "console")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",
    )
    monkeypatch.setenv(
        "JWT_SECRET",
        "test_secret_at_least_32_chars_long_for_pytest",
    )
    monkeypatch.setenv("CORS_ORIGINS", "[]")

    # Очистить кеш get_settings, чтобы каждый тест видел свои env-переменные
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def app() -> Generator[FastAPI, None, None]:
    """Создаёт изолированный экземпляр FastAPI для теста."""
    from app.main import create_app

    instance = create_app()
    yield instance


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """HTTP-клиент для тестирования FastAPI без поднятия uvicorn."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac
