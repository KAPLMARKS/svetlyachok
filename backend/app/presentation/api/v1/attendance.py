"""Эндпоинты учёта рабочего времени.

Матрица доступа:

| Эндпоинт                            | Admin                | Employee                         |
|-------------------------------------|----------------------|----------------------------------|
| GET  /api/v1/attendance             | OK (любой employee)  | OK (только свои логи)            |
| GET  /api/v1/attendance/summary     | OK (любой employee)  | OK (только свой employee_id)     |

Self-only проверка делается в use case (`ListAttendanceUseCase` /
`ComputeAttendanceSummaryUseCase`), не в роутере — там же поднимается
`ForbiddenError(code="attendance_self_only")`, который превращается в
RFC 7807 (HTTP 403) через стандартный exception handler.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.application.attendance.compute_summary import (
    AttendanceSummary,
    AttendanceSummaryQuery,
    ComputeAttendanceSummaryUseCase,
)
from app.application.attendance.list_attendance import (
    AttendancePage,
    ListAttendanceQuery,
    ListAttendanceUseCase,
)
from app.core.logging import get_logger
from app.domain.attendance.entities import AttendanceLog
from app.domain.attendance.value_objects import AttendanceStatus, WorkInterval
from app.domain.employees.entities import Employee
from app.presentation.dependencies import (
    get_compute_attendance_summary_use_case,
    get_current_user,
    get_list_attendance_use_case,
)
from app.presentation.schemas.attendance import (
    AttendanceLogResponse,
    AttendancePageResponse,
    AttendanceSummaryResponse,
)

log = get_logger(__name__)

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _to_response(entry: AttendanceLog) -> AttendanceLogResponse:
    """Доменная AttendanceLog → API DTO."""
    return AttendanceLogResponse(
        id=entry.id,
        employee_id=entry.employee_id,
        zone_id=entry.zone_id,
        started_at=entry.started_at,
        ended_at=entry.ended_at,
        last_seen_at=entry.last_seen_at,
        duration_seconds=entry.duration_seconds,
        status=entry.status.value,
    )


def _page_to_response(page: AttendancePage) -> AttendancePageResponse:
    return AttendancePageResponse(
        items=[_to_response(item) for item in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


def _summary_to_response(summary: AttendanceSummary) -> AttendanceSummaryResponse:
    return AttendanceSummaryResponse(
        employee_id=summary.employee_id,
        period_from=summary.period_from,
        period_to=summary.period_to,
        work_hours_total=summary.work_hours_total,
        lateness_count=summary.lateness_count,
        overtime_seconds_total=summary.overtime_seconds_total,
        sessions_count=summary.sessions_count,
    )


@router.get(
    "",
    response_model=AttendancePageResponse,
    status_code=status.HTTP_200_OK,
    summary="Список записей учёта посещаемости",
    description=(
        "Возвращает пагинированный список AttendanceLog с фильтрами. "
        "Admin видит любых сотрудников, employee — только свои логи "
        "(employee_id в фильтре подставляется автоматически)."
    ),
)
async def list_attendance(
    employee_id: int | None = Query(
        default=None, description="Фильтр по сотруднику (admin only без ограничений)"
    ),
    zone_id: int | None = Query(default=None, description="Фильтр по зоне"),
    status_filter: AttendanceStatus | None = Query(
        default=None,
        alias="status",
        description="Фильтр по статусу сессии",
    ),
    started_from: datetime | None = Query(
        default=None,
        description="Нижняя граница started_at (timezone-aware)",
    ),
    started_to: datetime | None = Query(
        default=None,
        description="Верхняя граница started_at (timezone-aware)",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: Employee = Depends(get_current_user),
    use_case: ListAttendanceUseCase = Depends(get_list_attendance_use_case),
) -> AttendancePageResponse:
    log.debug(
        "[attendance.endpoint.list] start",
        requesting_user_id=current_user.id,
        employee_id=employee_id,
        zone_id=zone_id,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )

    page = await use_case.execute(
        ListAttendanceQuery(
            requesting_user=current_user,
            employee_id=employee_id,
            zone_id=zone_id,
            status=status_filter,
            started_from=started_from,
            started_to=started_to,
            limit=limit,
            offset=offset,
        )
    )
    return _page_to_response(page)


@router.get(
    "/summary",
    response_model=AttendanceSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Агрегация по сотруднику за период",
    description=(
        "Считает work_hours_total, lateness_count, overtime_seconds_total и "
        "sessions_count за указанный период. Открытые сессии "
        "(`ended_at IS NULL`) исключены из аддитивных метрик. "
        "Admin может запросить любого сотрудника, employee — только себя."
    ),
)
async def get_attendance_summary(
    employee_id: int = Query(..., description="ID сотрудника"),
    period_from: datetime = Query(
        ...,
        alias="from",
        description="Начало периода (timezone-aware)",
    ),
    period_to: datetime = Query(
        ...,
        alias="to",
        description="Конец периода (timezone-aware, строго позже from)",
    ),
    current_user: Employee = Depends(get_current_user),
    use_case: ComputeAttendanceSummaryUseCase = Depends(
        get_compute_attendance_summary_use_case
    ),
) -> AttendanceSummaryResponse:
    log.debug(
        "[attendance.endpoint.summary] start",
        requesting_user_id=current_user.id,
        employee_id=employee_id,
        period_from=period_from.isoformat(),
        period_to=period_to.isoformat(),
    )

    summary = await use_case.execute(
        AttendanceSummaryQuery(
            requesting_user=current_user,
            employee_id=employee_id,
            period=WorkInterval(start=period_from, end=period_to),
        )
    )
    return _summary_to_response(summary)
