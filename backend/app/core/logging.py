"""Конфигурация структурированного логирования через structlog.

Настраивает stdlib logging как backend для structlog, добавляет процессоры:
- log level
- ISO timestamp
- callsite info (pathname/lineno) на DEBUG
- final renderer: JSON (production) или Console (development)

Использование:
    from app.core.logging import configure_logging, get_logger
    configure_logging(settings)
    log = get_logger(__name__)
    log.info("event happened", key="value")
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    """Инициализирует structlog + stdlib logging согласно settings.

    Должна вызываться один раз при старте приложения (в `main.create_app()`).
    Повторный вызов безопасен (re-binding structlog), но не нужен.

    Args:
        settings: загруженные настройки приложения.
    """
    log_level_int = logging.getLevelName(settings.log_level)

    # Базовая конфигурация stdlib logging — все логи идут в stdout
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level_int,
    )

    # Список процессоров structlog
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # На DEBUG-уровне добавляем callsite info для удобства отладки
    if settings.log_level == "DEBUG":
        shared_processors.append(
            structlog.processors.CallsiteParameterAdder(
                parameters={
                    structlog.processors.CallsiteParameter.PATHNAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                }
            )
        )

    # Финальный рендерер: JSON для production, Console для разработки
    final_processor: Processor
    if settings.log_format == "json":
        final_processor = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        final_processor = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, final_processor],
        wrapper_class=structlog.make_filtering_bound_logger(log_level_int),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Возвращает структурированный логгер.

    Args:
        name: имя логгера. По умолчанию — None (корневой).
              Принято передавать `__name__` модуля.

    Returns:
        Привязанный structlog logger.
    """
    logger: structlog.stdlib.BoundLogger = (
        structlog.get_logger(name) if name else structlog.get_logger()
    )
    return logger


def bind_correlation_id(correlation_id: str) -> None:
    """Привязывает correlation_id к текущему async-контексту.

    После этого все вызовы `get_logger()` в текущем контексте будут включать
    correlation_id в выводе автоматически.

    Используется в CorrelationIdMiddleware на каждый HTTP-запрос.
    """
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)


def clear_log_context() -> None:
    """Очищает все contextvars структурлога.

    Вызывается на выходе из middleware, чтобы данные одного запроса не утекали
    в логи другого (особенно важно при reuse async-task'ов).
    """
    structlog.contextvars.clear_contextvars()


# --- Helpers для тестирования ---


def _drop_color_message_key(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """Утилитарный процессор: удаляет color_message (используется ConsoleRenderer'ом)."""
    event_dict.pop("color_message", None)
    return event_dict
