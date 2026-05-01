"""Alembic environment в async-режиме (asyncpg + SQLAlchemy 2.x).

Настройки БД берём из pydantic-settings (`Settings.database_url`),
а не из alembic.ini. Это значит миграции запускаются с теми же
переменными окружения, что и приложение — нет рисков рассинхронизации.

ORM-модели импортируются ниже (через `app.infrastructure.db.orm`),
чтобы все таблицы зарегистрировались в `Base.metadata`. Без этого
autogenerate сравнивал бы пустую metadata с реальной БД и порождал
DROP'ы существующих таблиц.
"""

from __future__ import annotations

import asyncio
import logging
from logging.config import fileConfig
from urllib.parse import urlparse

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.infrastructure.db import orm  # noqa: F401  # регистрация моделей в Base.metadata
from app.infrastructure.db.base import Base

# Alembic Config object — даёт доступ к alembic.ini.
config = context.config

# Конфигурация Python logging из alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")


# Подмешиваем DSN из Settings в config (autogenerate и upgrade ходят в БД).
settings = get_settings()
_dsn = settings.database_url.unicode_string()
config.set_main_option("sqlalchemy.url", _dsn)
# urllib.parse работает с любым URL, включая MultiHostUrl Postgres.
# В логах используем только host — без credentials.
_db_host = urlparse(_dsn).hostname or "unknown"

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline-режим — генерирует SQL без подключения к БД.

    Полезно для предварительного просмотра миграции (`alembic upgrade head --sql`)
    или для деплоя в окружения без прямого доступа к Postgres.
    """
    url = config.get_main_option("sqlalchemy.url")
    logger.info("[alembic.env.offline] start url_host=%s", _db_host)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()

    logger.info("[alembic.env.offline] done")


def do_run_migrations(connection: Connection) -> None:
    """Sync-обёртка для run_migrations поверх async connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
        render_as_batch=False,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Online-режим: создаём async engine, выполняем миграции, освобождаем pool."""
    logger.info("[alembic.env.online] start url_host=%s", _db_host)

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()

    logger.info("[alembic.env.online] done")


def run_migrations_online() -> None:
    """Online-режим — запускает async loop под классический alembic CLI."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
