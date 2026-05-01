"""FastAPI exception handlers — преобразование исключений в RFC 7807 ответы.

Регистрирует обработчики для:
- AppError (доменные исключения) → status_code из исключения, code из class
- RequestValidationError (Pydantic) → 400 с validation_errors массивом
- Exception (catchall) → 500 без stacktrace в response, но с stacktrace в логе

Принципы:
- НЕ возвращать stacktrace в response payload (security)
- Включать correlation_id из structlog контекста для трассировки
- Логировать на правильном уровне: WARN для AppError, ERROR для unhandled
"""

from __future__ import annotations

from http import HTTPStatus

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.domain.shared.exceptions import AppError
from app.presentation.schemas.errors import (
    ProblemDetailResponse,
    ValidationErrorDetail,
)

log = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Регистрирует все exception handlers на FastAPI app.

    Должна вызываться один раз в `main.create_app()` после создания app.
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        correlation_id = _current_correlation_id()
        log.warning(
            "[ExceptionHandler.app_error] %s",
            exc.code,
            code=exc.code,
            status_code=exc.status_code,
            path=request.url.path,
            method=request.method,
            details=exc.details,
        )

        problem = ProblemDetailResponse(
            title=HTTPStatus(exc.status_code).phrase,
            status=exc.status_code,
            detail=exc.message,
            instance=str(request.url.path),
            code=exc.code,
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        correlation_id = _current_correlation_id()
        errors = exc.errors()
        log.info(
            "[ExceptionHandler.validation] payload validation failed",
            path=request.url.path,
            method=request.method,
            errors_count=len(errors),
        )

        problem = ProblemDetailResponse(
            title=HTTPStatus.BAD_REQUEST.phrase,
            status=status.HTTP_400_BAD_REQUEST,
            detail="Request payload validation failed",
            instance=str(request.url.path),
            code="validation_error",
            correlation_id=correlation_id,
            validation_errors=[
                ValidationErrorDetail(
                    loc=list(err.get("loc", [])),
                    msg=str(err.get("msg", "")),
                    type=str(err.get("type", "")),
                )
                for err in errors
            ],
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        correlation_id = _current_correlation_id()
        log.error(
            "[ExceptionHandler.unhandled] unexpected error",
            path=request.url.path,
            method=request.method,
            exc_type=type(exc).__name__,
            exc_info=True,
        )

        problem = ProblemDetailResponse(
            title=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support with correlation ID.",
            instance=str(request.url.path),
            code="internal_error",
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )


def _current_correlation_id() -> str | None:
    """Извлекает correlation_id из текущего structlog контекста."""
    bound = structlog.contextvars.get_contextvars()
    value = bound.get("correlation_id")
    return str(value) if value is not None else None
