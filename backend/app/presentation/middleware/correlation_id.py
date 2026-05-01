"""Middleware для проброса correlation_id через HTTP-запрос.

Извлекает X-Correlation-ID из заголовка запроса (или генерирует новый),
биндит в structlog контекст, добавляет в response header.

Принципы:
- Один correlation_id на запрос — для трассировки в логах
- Совместимый стандарт (X-Correlation-ID или X-Request-ID) — клиенты могут
  передавать свой ID и связывать логи на их стороне с серверными
- На выходе очищаем contextvars, чтобы не утекало в следующий запрос
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import (
    bind_correlation_id,
    clear_log_context,
    get_logger,
)

CORRELATION_ID_HEADER = "X-Correlation-ID"

log = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """ASGI middleware: correlation_id для каждого запроса."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = (
            request.headers.get(CORRELATION_ID_HEADER) or _generate_correlation_id()
        )
        bind_correlation_id(correlation_id)

        start_time = time.perf_counter()
        log.debug(
            "[CorrelationIdMiddleware.dispatch] start",
            method=request.method,
            path=request.url.path,
            correlation_id=correlation_id,
        )

        response: Response
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log.error(
                "[CorrelationIdMiddleware.dispatch] unhandled exception",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                exc_info=True,
            )
            clear_log_context()
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers[CORRELATION_ID_HEADER] = correlation_id

        log.info(
            "[CorrelationIdMiddleware.dispatch] done",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )

        clear_log_context()
        return response


def _generate_correlation_id() -> str:
    """UUID4 без дефисов — компактнее для логов и URL."""
    return uuid.uuid4().hex
