"""Корневой pytest conftest: общие fixtures для всех тестов.

Принципы:
- Юнит-тесты (`-m unit` или без маркера) не требуют PostgreSQL и работают
  на фиктивных DSN (через `_set_test_env`).
- Интеграционные тесты (`-m integration`) поднимают тестовый Postgres:
    - Если задан `TEST_DATABASE_URL` — используем эту БД (CI и локальные
      инстансы Postgres).
    - Иначе пытаемся поднять testcontainer-postgres (требует Docker).
    - Если Docker недоступен — тесты будут пропущены через
      `pytest.skip` в session-scoped fixture.
- Каждый интеграционный тест получает «чистую» БД через savepoint-rollback
  на уровне function-scope: миграции применяются один раз на сессию,
  а изменения откатываются после каждого теста.
- Settings cache (lru_cache) очищается между тестами.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, AsyncIterator, Generator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Базовые юнит-тестовые fixtures (без БД)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_test_env(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Автоматически выставляет минимально необходимые env-переменные.

    Применяется ко ВСЕМ тестам. Если тест помечен как `integration` и
    в окружении доступен `TEST_DATABASE_URL`, используем его как
    `DATABASE_URL`, иначе остаётся фиктивный DSN.
    """
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "console")

    is_integration = "integration" in request.keywords
    test_db_url = os.environ.get("TEST_DATABASE_URL")
    if is_integration and test_db_url:
        monkeypatch.setenv("DATABASE_URL", test_db_url)
    else:
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
    """Создаёт изолированный экземпляр FastAPI для теста (без БД)."""
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


# ---------------------------------------------------------------------------
# Интеграционные fixtures (с настоящей БД)
# ---------------------------------------------------------------------------


def _resolve_async_dsn(raw_dsn: str) -> str:
    """Гарантирует наличие драйвера asyncpg в DSN.

    testcontainers возвращает `postgresql+psycopg2://...`; нам нужен
    `postgresql+asyncpg://...` для SQLAlchemy async.
    """
    if raw_dsn.startswith("postgresql+asyncpg://"):
        return raw_dsn
    if raw_dsn.startswith("postgresql+psycopg2://"):
        return raw_dsn.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if raw_dsn.startswith("postgresql://"):
        return raw_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw_dsn


@pytest.fixture(scope="session")
def postgres_dsn() -> Generator[str, None, None]:
    """Возвращает DSN тестового Postgres.

    Стратегия:
    1. Если задан `TEST_DATABASE_URL` — используем готовую БД.
    2. Иначе пытаемся поднять testcontainer postgres:16-alpine.
    3. Если Docker недоступен — пропускаем интеграционные тесты.
    """
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        yield _resolve_async_dsn(explicit)
        return

    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip(
            "testcontainers не установлен; задайте TEST_DATABASE_URL или установите [dev]-зависимости"
        )

    try:
        container = PostgresContainer("postgres:16-alpine")
        container.start()
    except Exception as exc:
        pytest.skip(f"Docker недоступен для testcontainer-postgres: {exc!r}")

    try:
        yield _resolve_async_dsn(container.get_connection_url())
    finally:
        container.stop()


@pytest.fixture(scope="session")
async def migrated_db(postgres_dsn: str) -> AsyncGenerator[str, None]:
    """Применяет `alembic upgrade head` к тестовой БД один раз на сессию.

    Возвращает тот же DSN. Все интеграционные тесты получают БД с
    актуальной схемой, изолируясь друг от друга через savepoint в
    `db_session` / `db_sessionmaker`.
    """
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", postgres_dsn)

    # Alembic env.py кладёт URL из Settings в config; временно подменяем
    # переменную окружения, чтобы он подхватил наш DSN.
    prev_dsn = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = postgres_dsn
    try:
        from app.core.config import get_settings

        get_settings.cache_clear()
        command.upgrade(cfg, "head")
    finally:
        if prev_dsn is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev_dsn
        get_settings.cache_clear()

    yield postgres_dsn


@pytest.fixture
async def db_engine(migrated_db: str) -> AsyncIterator[AsyncEngine]:
    """Async engine, привязанный к мигрированной тестовой БД."""
    engine = create_async_engine(
        migrated_db,
        pool_pre_ping=True,
        connect_args={"server_settings": {"jit": "off"}},
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Function-scoped транзакционная сессия с автоматическим rollback.

    Паттерн: открываем connection + begin (внешняя транзакция) +
    AsyncSession поверх savepoint. Любые коммиты в тесте обновляют
    только savepoint; внешняя транзакция в конце откатывается, и БД
    остаётся «как до теста».
    """
    async with db_engine.connect() as connection:
        outer_tx = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False)
            try:
                yield session
            finally:
                await session.close()
        finally:
            await outer_tx.rollback()


@pytest.fixture
async def db_sessionmaker(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """async_sessionmaker для тестов, которым нужна именно фабрика."""
    return async_sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest.fixture
async def app_with_db(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[FastAPI, None]:
    """FastAPI app с подменённой `get_db_sessionmaker_dep` на тестовую фабрику."""
    from app.infrastructure.db import session as db_session_module
    from app.main import create_app
    from app.presentation.dependencies import get_db_sessionmaker_dep

    instance = create_app()
    instance.dependency_overrides[get_db_sessionmaker_dep] = lambda: db_sessionmaker

    # Подмена module-level singleton, чтобы lifespan и любые внутренние
    # обращения к `get_sessionmaker()` тоже видели тестовую фабрику.
    prev_sm = db_session_module._sessionmaker
    db_session_module._sessionmaker = db_sessionmaker
    try:
        yield instance
    finally:
        instance.dependency_overrides.clear()
        db_session_module._sessionmaker = prev_sm


@pytest.fixture
async def client_with_db(app_with_db: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """HTTP-клиент поверх app с подключённой БД."""
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
