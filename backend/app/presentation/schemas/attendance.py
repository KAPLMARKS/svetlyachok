"""Pydantic-схемы API учёта посещаемости (`/api/v1/attendance`).

`AttendanceLogResponse` — DTO записи посещаемости. `status` сериализуется
строкой (значение enum), а не объектом, для совместимости с фронтом
без зависимости от Python enum-типа.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttendanceLogResponse(BaseModel):
    """Запись о пребывании сотрудника в зоне."""

    model_config = ConfigDict(extra="forbid")

    id: int
    employee_id: int
    zone_id: int
    started_at: datetime
    ended_at: datetime | None
    last_seen_at: datetime
    duration_seconds: int | None
    status: str  # AttendanceStatus.value


class AttendancePageResponse(BaseModel):
    """Страница записей с пагинацией."""

    model_config = ConfigDict(extra="forbid")

    items: list[AttendanceLogResponse]
    total: int
    limit: int
    offset: int


class AttendanceSummaryResponse(BaseModel):
    """Агрегация по сотруднику за период."""

    model_config = ConfigDict(extra="forbid")

    employee_id: int
    period_from: datetime
    period_to: datetime
    work_hours_total: float
    lateness_count: int
    overtime_seconds_total: int
    sessions_count: int
