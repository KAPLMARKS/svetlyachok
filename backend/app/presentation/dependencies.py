"""Общие FastAPI-зависимости для presentation-слоя.

Тонкая обёртка над инфраструктурными singleton'ами, чтобы FastAPI
дернул их через `Depends()`. Это позволяет тестам подменять реализации
через `app.dependency_overrides[...]` без monkey-patch'а module-level
переменных.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.session import get_sessionmaker


def get_db_sessionmaker_dep() -> async_sessionmaker[AsyncSession]:
    """FastAPI dependency: возвращает текущую фабрику AsyncSession.

    Используется компонентами, которым нужна именно фабрика (например,
    healthcheck открывает свою короткую сессию). Транзакционная сессия
    для CRUD-роутов берётся через `get_session` из infrastructure.
    """
    return get_sessionmaker()
