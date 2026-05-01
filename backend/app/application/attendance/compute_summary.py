"""Use case `ComputeAttendanceSummaryUseCase` — агрегация по периоду.

Считает по сотруднику за заданный период:

- `work_hours_total`: суммарные часы в рабочих зонах (`workplace`),
  только по закрытым сессиям (`ended_at IS NOT NULL`).
- `lateness_count`: число сессий со статусом `LATE`.
- `overtime_seconds_total`: суммарные секунды со статусом `OVERTIME`
  (упрощённо считаем всю длительность OVERTIME-сессии; точный
  расчёт overtime-секунд относительно `schedule_end` — в следующей итерации).
- `sessions_count`: общее число сессий в периоде (включая открытые).

Открытые сессии (`ended_at IS NULL`) исключены из всех аддитивных метрик
(`work_hours_total`, `overtime_seconds_total`), так как их продолжительность
ещё не известна, но учтены в `sessions_count`.

Self-only проверка как в ListAttendanceUseCase.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.logging import get_logger
from app.domain.attendance.repositories import AttendanceRepository
from app.domain.attendance.value_objects import AttendanceStatus, WorkInterval
from app.domain.employees.entities import Employee, Role
from app.domain.shared.exceptions import ForbiddenError
from app.domain.zones.entities import ZoneType
from app.domain.zones.repositories import ZoneRepository

log = get_logger(__name__)


@dataclass(frozen=True)
class AttendanceSummaryQuery:
    """Параметры запроса агрегации."""

    requesting_user: Employee
    employee_id: int
    period: WorkInterval


@dataclass(frozen=True)
class AttendanceSummary:
    """Результат агрегации по сотруднику за период."""

    employee_id: int
    period_from: datetime
    period_to: datetime
    work_hours_total: float
    lateness_count: int
    overtime_seconds_total: int
    sessions_count: int


class ComputeAttendanceSummaryUseCase:
    """Считает агрегированные показатели присутствия за период."""

    def __init__(
        self,
        attendance_repo: AttendanceRepository,
        zone_repo: ZoneRepository,
    ) -> None:
        self._attendance_repo = attendance_repo
        self._zone_repo = zone_repo

    async def execute(self, query: AttendanceSummaryQuery) -> AttendanceSummary:
        log.debug(
            "[attendance.summary.execute] start",
            requesting_user_id=query.requesting_user.id,
            employee_id=query.employee_id,
            period_from=query.period.start.isoformat(),
            period_to=query.period.end.isoformat(),
        )

        self._enforce_self_only(query)

        # Берём ВСЕ записи в периоде. Размер выборки на пилотных данных
        # умещается в памяти (≤ десятки тысяч записей за период).
        # Для production с миллионами строк потребуется агрегация на стороне БД.
        logs = await self._attendance_repo.list(
            employee_id=query.employee_id,
            started_from=query.period.start,
            started_to=query.period.end,
            limit=100_000,
            offset=0,
        )

        # Получаем zone-id'ы рабочих зон, чтобы посчитать work_hours_total.
        workplace_zone_ids = await self._collect_workplace_zone_ids()

        work_seconds_total = 0
        lateness_count = 0
        overtime_seconds_total = 0
        for entry in logs:
            if entry.status is AttendanceStatus.LATE:
                lateness_count += 1
            if entry.duration_seconds is None:
                # Открытая сессия: исключаем из аддитивных метрик.
                continue
            if entry.status is AttendanceStatus.OVERTIME:
                overtime_seconds_total += entry.duration_seconds
            if entry.zone_id in workplace_zone_ids:
                work_seconds_total += entry.duration_seconds

        result = AttendanceSummary(
            employee_id=query.employee_id,
            period_from=query.period.start,
            period_to=query.period.end,
            work_hours_total=round(work_seconds_total / 3600, 4),
            lateness_count=lateness_count,
            overtime_seconds_total=overtime_seconds_total,
            sessions_count=len(logs),
        )
        log.info(
            "[attendance.summary.execute] done",
            employee_id=result.employee_id,
            work_hours_total=result.work_hours_total,
            lateness_count=result.lateness_count,
            overtime_seconds_total=result.overtime_seconds_total,
            sessions_count=result.sessions_count,
        )
        return result

    async def _collect_workplace_zone_ids(self) -> set[int]:
        """Возвращает множество id зон с типом WORKPLACE.

        Кэширование оставлено вызывающему — на пилоте зон ≤ десятка,
        запрос дешёвый.
        """
        zones = await self._zone_repo.list(
            type_filter=ZoneType.WORKPLACE, limit=1000, offset=0
        )
        return {zone.id for zone in zones}

    @staticmethod
    def _enforce_self_only(query: AttendanceSummaryQuery) -> None:
        user = query.requesting_user
        if user.role is Role.ADMIN:
            return
        if query.employee_id != user.id:
            log.warning(
                "[attendance.summary.execute] forbidden_other_employee",
                requesting_user_id=user.id,
                requested_employee_id=query.employee_id,
            )
            raise ForbiddenError(
                code="attendance_self_only",
                message=(
                    "Сотрудник может смотреть только свою агрегацию посещаемости"
                ),
            )
