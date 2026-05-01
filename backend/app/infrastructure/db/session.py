"""Async-инфраструктура SQLAlchemy: engine, sessionmaker, FastAPI dependency.

Lifecycle управляется через `init_engine` (на startup) и `dispose_engine`
(на shutdown). Все компоненты — module-level singletons, чтобы FastAPI
Depends() и фоновые задачи (например, seed-скрипт) использовали одну и ту же
фабрику сессий.

Использование как FastAPI dependency:

    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.infrastructure.db.session import get_session

    async def handler(session: AsyncSession = Depends(get_session)):
        ...

`get_session()` сам управляет транзакцией: коммитит при успехе, откатывает
при исключении и гарантированно закрывает сессию.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> AsyncEngine:
    """Создаёт async engine + sessionmaker и сохраняет их как module-level singletons.

    Должно быть вызвано один раз на старте приложения (FastAPI lifespan).
    Повторный вызов — no-op (возвращает уже существующий engine), чтобы не
    плодить пулы при горячем перезапуске тестов.

    Параметры пула:
    - pool_size=5, max_overflow=10 — для пилота с ~50 пользователями более
      чем достаточно
    - pool_pre_ping=True — отлавливает разорванные соединения (recycle на
      asyncpg иногда не покрывает long-living коннекты в облачных Postgres)
    - pool_recycle=1800 — пересоздавать соединение раз в 30 минут
    - server_settings={"jit": "off"} — рекомендация Supabase: для коротких
      запросов JIT часто ухудшает latency больше, чем помогает
    """
    global _engine, _sessionmaker

    if _engine is not None:
        log.debug("[db.session.init_engine] engine already initialised, returning existing")
        return _engine

    dsn = settings.database_url.unicode_string()
    echo_sql = settings.environment == "development" and settings.log_level == "DEBUG"

    _engine = create_async_engine(
        dsn,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=echo_sql,
        connect_args={"server_settings": {"jit": "off"}},
    )

    _sessionmaker = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # urlparse работает с любым URL, в т.ч. MultiHostUrl. В логи кладём
    # только host и path — без credentials.
    parsed = urlparse(dsn)
    log.info(
        "[db.session.init_engine] engine created",
        host=parsed.hostname,
        path=parsed.path,
        pool_size=5,
        max_overflow=10,
        echo_sql=echo_sql,
    )
    return _engine


async def dispose_engine() -> None:
    """Корректно закрывает пул соединений engine.

    Должно быть вызвано на shutdown приложения. После этого вызов
    `get_sessionmaker()` поднимет ошибку — это намеренно, чтобы
    словить use-after-shutdown.
    """
    global _engine, _sessionmaker

    if _engine is None:
        log.debug("[db.session.dispose_engine] engine not initialised, nothing to dispose")
        return

    await _engine.dispose()
    _engine = None
    _sessionmaker = None
    log.info("[db.session.dispose_engine] engine disposed")


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Возвращает фабрику сессий. Падает, если engine не инициализирован.

    Используется компонентами, которым нужна именно фабрика, а не одна
    конкретная сессия (например, healthcheck открывает короткоживущую
    сессию для `SELECT 1`).
    """
    if _sessionmaker is None:
        raise RuntimeError(
            "Database engine is not initialised. "
            "Call init_engine(settings) on application startup."
        )
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: открывает сессию, коммитит при успехе, откатывает при ошибке.

    Yields один экземпляр AsyncSession на запрос. Транзакция управляется
    автоматически:

    - Хендлер отработал без исключений → `commit()`
    - Хендлер поднял исключение → `rollback()` + rethrow
    - В любом случае — `close()` в `finally`

    Этот контракт совпадает с FastAPI dependency-протоколом: исключения,
    поднятые в хендлере, прокидываются сюда через генератор.
    """
    sessionmaker = get_sessionmaker()
    session = sessionmaker()

    log.debug("[db.session] session opened")
    try:
        yield session
    except Exception as exc:
        await session.rollback()
        log.warning(
            "[db.session] rollback due to exception",
            exc_type=type(exc).__name__,
        )
        raise
    else:
        await session.commit()
        log.debug("[db.session] session committed")
    finally:
        await session.close()
        log.debug("[db.session] session closed")
