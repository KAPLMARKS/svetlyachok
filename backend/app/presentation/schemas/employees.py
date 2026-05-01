"""Pydantic-схемы CRUD сотрудников.

`EmployeeResponse` намеренно не содержит `hashed_password` — даже
маскированный hash наружу не пробрасываем.
"""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app.domain.employees.entities import Role


class EmployeeCreateRequest(BaseModel):
    """POST /api/v1/employees — admin создаёт сотрудника."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    role: Role
    initial_password: SecretStr = Field(..., min_length=8, max_length=128)
    schedule_start: time | None = None
    schedule_end: time | None = None


class EmployeeUpdateRequest(BaseModel):
    """PATCH /api/v1/employees/{id} — все поля опциональны."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: Role | None = None
    schedule_start: time | None = None
    schedule_end: time | None = None
    # Явные флаги «очистить расписание»: иначе нельзя различить
    # «не передал поле» (PATCH-семантика «не менять») и «передал null»
    # («убрать»). Pydantic эти семантики путает на JSON.
    clear_schedule_start: bool = False
    clear_schedule_end: bool = False


class ChangePasswordRequest(BaseModel):
    """POST /api/v1/employees/{id}/password.

    Если вызывает admin для другого пользователя — `old_password`
    не передаётся (admin-reset режим). Если сотрудник меняет свой —
    `old_password` обязателен; endpoint валидирует это правило.
    """

    model_config = ConfigDict(extra="forbid")

    new_password: SecretStr = Field(..., min_length=8, max_length=128)
    old_password: SecretStr | None = None


class EmployeeResponse(BaseModel):
    """Публичная информация о сотруднике (без hashed_password!)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    schedule_start: time | None = None
    schedule_end: time | None = None


class EmployeesPageResponse(BaseModel):
    """Страница сотрудников с пагинацией."""

    model_config = ConfigDict(extra="forbid")

    items: list[EmployeeResponse]
    total: int
    limit: int
    offset: int
