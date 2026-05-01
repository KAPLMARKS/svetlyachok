"""Проверка доступности БД для healthcheck endpoint.

Делает короткий `SELECT 1` через переданную фабрику сессий, оборачивает
в таймаут (по умолчанию 2 секунды) и нормализует все исключения в
строковый литерал `"ok"` / `"fail"`. Никогда не пробрасывает наружу:
healthcheck должен оставаться отзывчивым даже при катастрофическом
состоянии БД.
"""

from __future__ import annotations

import asyncio
import time
from typing import Literal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger

log = get_logger(__name__)


HealthStatus = Literal["ok", "fail"]


async def check_database(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    timeout_seconds: float = 2.0,
) -> HealthStatus:
    """Возвращает `"ok"` если БД отвечает на `SELECT 1`, иначе `"fail"`.

    Параметры:
        session_factory: фабрика, открывающая короткоживущую сессию
            именно под healthcheck. Не используем зависимость
            `get_session` намеренно: ей нужна транзакция, а нам — только
            быстрый probe.
        timeout_seconds: жёсткий лимит на весь probe. Если БД не ответит
            за это время — считаем `"fail"` без ожидания TCP-таймаута
            (тот по умолчанию ~30s, что для healthcheck недопустимо).
    """
    log.debug("[db.healthcheck] start", timeout=timeout_seconds)

    started = time.perf_counter()
    try:
        async with asyncio.timeout(timeout_seconds):
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
    except TimeoutError:
        log.warning(
            "[db.healthcheck] fail",
            reason="timeout",
            exc_type="TimeoutError",
            timeout=timeout_seconds,
        )
        return "fail"
    except SQLAlchemyError as exc:
        log.warning(
            "[db.healthcheck] fail",
            reason="sqlalchemy_error",
            exc_type=type(exc).__name__,
        )
        return "fail"
    except OSError as exc:
        # ConnectionRefusedError, gaierror и др. — БД физически недоступна.
        log.warning(
            "[db.healthcheck] fail",
            reason="connection_error",
            exc_type=type(exc).__name__,
        )
        return "fail"
    except Exception as exc:  # pragma: no cover
        # Нестандартный сбой (например, инвалидный engine после dispose).
        # Логируем тип исключения и считаем "fail" — health не должен падать.
        log.warning(
            "[db.healthcheck] fail",
            reason="unexpected",
            exc_type=type(exc).__name__,
        )
        return "fail"

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    log.debug("[db.healthcheck] ok", latency_ms=latency_ms)
    return "ok"
