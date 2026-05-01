"""Use case `RecordAttendanceUseCase` — фиксирует появление сотрудника в зоне.

Запускается на каждом успешном `/api/v1/positioning/classify`. Управляет
жизненным циклом открытой `AttendanceLog`:

1. Нет открытой → создать новую с `started_at = now`, `last_seen_at = now`.
2. Есть открытая, та же зона, `now - last_seen_at <= timeout` → продлить
   (UPDATE last_seen_at).
3. Есть открытая, та же зона, `now - last_seen_at > timeout` → закрыть
   с `ended_at = last_seen_at`, открыть новую с `started_at = now`.
4. Есть открытая, другая зона → закрыть с `ended_at = now`, открыть
   новую с `started_at = now`, `zone_id = новой`.

Статус определяется доменным сервисом `compute_status_on_open` при
открытии и `compute_final_status` при закрытии (повышение до OVERTIME).

Если у сотрудника нет графика, статус всегда PRESENT (без late/overtime).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.logging import get_logger
from app.domain.attendance.entities import AttendanceLog
from app.domain.attendance.repositories import AttendanceRepository
from app.domain.attendance.services import (
    compute_final_status,
    compute_status_on_open,
)
from app.domain.attendance.value_objects import AttendanceStatus
from app.domain.employees.repositories import EmployeeRepository
from app.domain.shared.exceptions import NotFoundError, ValidationError
from app.domain.zones.entities import ZoneType

log = get_logger(__name__)


@dataclass(frozen=True)
class RecordAttendanceCommand:
    """Входные данные для RecordAttendanceUseCase.

    Передаётся из presentation-слоя сразу после успешной классификации.
    `now` инжектируется явно, чтобы быть тестируемым (а не брать
    `datetime.now(tz=UTC)` внутри use case).
    """

    employee_id: int
    zone_id: int
    zone_type: ZoneType
    now: datetime


class RecordAttendanceUseCase:
    """Открытие/закрытие/продление сессии присутствия по результату классификации."""

    def __init__(
        self,
        attendance_repo: AttendanceRepository,
        employee_repo: EmployeeRepository,
        inactivity_timeout: timedelta,
    ) -> None:
        self._attendance_repo = attendance_repo
        self._employee_repo = employee_repo
        self._inactivity_timeout = inactivity_timeout

    async def execute(self, cmd: RecordAttendanceCommand) -> AttendanceLog:
        log.debug(
            "[attendance.record.execute] start",
            employee_id=cmd.employee_id,
            zone_id=cmd.zone_id,
            zone_type=cmd.zone_type.value,
            now=cmd.now.isoformat(),
        )

        if cmd.now.tzinfo is None:
            raise ValidationError(
                code="attendance_now_must_be_timezone_aware",
                message="now должен быть timezone-aware (предпочтительно UTC)",
            )

        employee = await self._employee_repo.get_by_id(cmd.employee_id)
        if employee is None:
            log.warning(
                "[attendance.record.execute] employee_not_found",
                employee_id=cmd.employee_id,
            )
            raise NotFoundError(
                code="employee_not_found",
                message=f"Employee id={cmd.employee_id} не найден",
            )

        open_session = await self._attendance_repo.get_open_session_for_employee(
            cmd.employee_id
        )

        # Ветка 1: нет открытой сессии → открываем новую.
        if open_session is None:
            return await self._open_new_session(cmd, employee.schedule_start)

        inactivity = cmd.now - open_session.last_seen_at

        # Ветки 2 и 3: та же зона.
        if open_session.zone_id == cmd.zone_id:
            if inactivity <= self._inactivity_timeout:
                # Ветка 2: продлеваем сессию.
                extended = open_session.extend(cmd.now)
                result = await self._attendance_repo.update(extended)
                log.info(
                    "[attendance.record.execute] session_extended",
                    attendance_log_id=result.id,
                    employee_id=result.employee_id,
                    zone_id=result.zone_id,
                    inactivity_seconds=int(inactivity.total_seconds()),
                )
                return result

            # Ветка 3: таймаут в той же зоне → закрываем по last_seen_at,
            # открываем новую от now.
            log.info(
                "[attendance.record.execute] timeout_close_then_open",
                attendance_log_id=open_session.id,
                employee_id=open_session.employee_id,
                zone_id=open_session.zone_id,
                inactivity_seconds=int(inactivity.total_seconds()),
                timeout_seconds=int(self._inactivity_timeout.total_seconds()),
            )
            await self._close_session(
                open_session,
                ended_at=open_session.last_seen_at,
                schedule_end=employee.schedule_end,
            )
            return await self._open_new_session(cmd, employee.schedule_start)

        # Ветка 4: другая зона → закрываем по now, открываем новую от now.
        log.info(
            "[attendance.record.execute] zone_changed_close_then_open",
            attendance_log_id=open_session.id,
            employee_id=open_session.employee_id,
            from_zone_id=open_session.zone_id,
            to_zone_id=cmd.zone_id,
        )
        await self._close_session(
            open_session,
            ended_at=cmd.now,
            schedule_end=employee.schedule_end,
        )
        return await self._open_new_session(cmd, employee.schedule_start)

    async def _open_new_session(
        self,
        cmd: RecordAttendanceCommand,
        schedule_start,
    ) -> AttendanceLog:
        """Создаёт и сохраняет новую открытую AttendanceLog."""
        status = compute_status_on_open(
            started_at=cmd.now,
            zone_type=cmd.zone_type,
            schedule_start=schedule_start,
        )
        log_entry = AttendanceLog(
            id=0,  # будет проставлен репозиторием при INSERT
            employee_id=cmd.employee_id,
            zone_id=cmd.zone_id,
            started_at=cmd.now,
            ended_at=None,
            last_seen_at=cmd.now,
            duration_seconds=None,
            status=status,
        )
        result = await self._attendance_repo.add(log_entry)
        log.info(
            "[attendance.record.execute] session_opened",
            attendance_log_id=result.id,
            employee_id=result.employee_id,
            zone_id=result.zone_id,
            status=result.status.value,
        )
        return result

    async def _close_session(
        self,
        session: AttendanceLog,
        *,
        ended_at: datetime,
        schedule_end,
    ) -> AttendanceLog:
        """Закрывает существующую сессию: ended_at + duration + final status."""
        # При закрытии текущий status уже установлен при открытии (PRESENT/LATE);
        # повышаем до OVERTIME, если ended_at позже schedule_end.
        current_status: AttendanceStatus = session.status
        final_status = compute_final_status(
            started_at=session.started_at,
            ended_at=ended_at,
            current_status=current_status,
            schedule_end=schedule_end,
        )
        closed = session.close(ended_at=ended_at, status=final_status)
        result = await self._attendance_repo.update(closed)
        log.info(
            "[attendance.record.execute] session_closed",
            attendance_log_id=result.id,
            employee_id=result.employee_id,
            zone_id=result.zone_id,
            duration_seconds=result.duration_seconds,
            status=result.status.value,
        )
        return result
