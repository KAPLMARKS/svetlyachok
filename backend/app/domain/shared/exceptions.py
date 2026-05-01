"""Доменные исключения проекта.

Базовый класс AppError + конкретные ошибки с правильными HTTP status codes.
Используются в use cases и domain services. Преобразование в RFC 7807
Problem Details — в presentation/exception_handlers.py.

Принцип: исключение НЕ знает про HTTP, FastAPI или JSON.
Только ошибочный код (machine-readable), сообщение, и hint для status_code.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Базовое доменное исключение.

    Атрибуты:
        code: machine-readable идентификатор ошибки (snake_case).
              Используется клиентами для обработки конкретных случаев.
              Пример: "employee_not_found", "invalid_email_format".
        message: человеко-читаемое сообщение (для логов и detail-поля API).
        status_code: подсказка для HTTP exception handler (по умолчанию 500).
        details: опциональный словарь с контекстом (validation errors, IDs и т.п.).
    """

    code: str = "app_error"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message: str = message
        if code is not None:
            self.code = code
        self.details: dict[str, Any] = details or {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, status={self.status_code}, message={self.message!r})"


class ValidationError(AppError):
    """Невалидные данные на входе use case.

    HTTP 400 Bad Request.
    """

    code = "validation_error"
    status_code = 400


class NotFoundError(AppError):
    """Запрашиваемый ресурс не найден.

    HTTP 404 Not Found.
    """

    code = "not_found"
    status_code = 404


class ConflictError(AppError):
    """Конфликт состояния (дубль, нарушение инварианта).

    HTTP 409 Conflict.
    Пример: попытка создать сотрудника с уже существующим email.
    """

    code = "conflict"
    status_code = 409


class UnauthorizedError(AppError):
    """Аутентификация не пройдена (нет токена / токен невалиден).

    HTTP 401 Unauthorized.
    """

    code = "unauthorized"
    status_code = 401


class ForbiddenError(AppError):
    """Аутентификация пройдена, но прав на действие нет.

    HTTP 403 Forbidden.
    """

    code = "forbidden"
    status_code = 403
