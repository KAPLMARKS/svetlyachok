"""Pydantic-схемы ответов об ошибках по RFC 7807 Problem Details.

RFC 7807: https://datatracker.ietf.org/doc/html/rfc7807

Базовый формат:
{
  "type": "https://example.com/probs/...",
  "title": "Short, human-readable summary",
  "status": 404,
  "detail": "Detailed message about this specific occurrence",
  "instance": "/api/v1/employees/123"
}

Расширения проекта:
- code — machine-readable код ошибки (для клиентской логики)
- correlation_id — для связи с логами на сервере
- validation_errors — список ошибок валидации (для 400)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationErrorDetail(BaseModel):
    """Одна ошибка валидации Pydantic-схемы."""

    loc: list[str | int] = Field(
        default_factory=list,
        description="Путь к полю с ошибкой (например, ['body', 'employee_id']).",
    )
    msg: str = Field(..., description="Текст ошибки.")
    type: str = Field(..., description="Тип ошибки (Pydantic error type).")


class ProblemDetailResponse(BaseModel):
    """RFC 7807 Problem Details + расширения проекта."""

    type: str = Field(
        default="about:blank",
        description="URI идентификатор типа проблемы. По умолчанию 'about:blank'.",
    )
    title: str = Field(..., description="Краткое описание (соответствует HTTP reason).")
    status: int = Field(..., ge=400, le=599, description="HTTP status code.")
    detail: str = Field(
        ...,
        description="Детальное описание этого конкретного случая (для пользователя/логов).",
    )
    instance: str | None = Field(
        default=None,
        description="URI запроса, в котором произошла ошибка.",
    )

    # --- Расширения проекта ---

    code: str = Field(
        ...,
        description="Machine-readable код ошибки. Используется клиентом для обработки.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="ID корреляции из X-Correlation-ID header (для трассировки в логах).",
    )
    validation_errors: list[ValidationErrorDetail] | None = Field(
        default=None,
        description="Список ошибок валидации (только для 400 Validation Error).",
    )
