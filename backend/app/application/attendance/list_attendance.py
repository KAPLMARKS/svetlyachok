"""Use case `ListAttendanceUseCase` — пагинированный список сессий присутствия.

Self-only проверка для роли `EMPLOYEE`: рядовой сотрудник видит только
свои логи. Если employee запрашивает чужой `employee_id` — `ForbiddenError`.
Если не указывает фильтр `employee_id` вовсе — принудительно подставляется
его собственный `id` (видит только себя).

Admin видит любых сотрудников без ограничений.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.logging import get_logger
from app.domain.attendance.entities import AttendanceLog
from app.domain.attendance.repositories import AttendanceRepository
from app.domain.attendance.value_objects import AttendanceStatus
from app.domain.employees.entities import Employee, Role
from app.domain.shared.exceptions import ForbiddenError

log = get_logger(__name__)


@dataclass(frozen=True)
class ListAttendanceQuery:
    """Входные параметры для ListAttendanceUseCase."""

    requesting_user: Employee
    employee_id: int | None = None
    zone_id: int | None = None
    status: AttendanceStatus | None = None
    started_from: datetime | None = None
    started_to: datetime | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class AttendancePage:
    """Результат пагинированной выборки."""

    items: list[AttendanceLog]
    total: int
    limit: int
    offset: int


class ListAttendanceUseCase:
    """Возвращает страницу сессий присутствия с учётом фильтров и роли."""

    def __init__(self, attendance_repo: AttendanceRepository) -> None:
        self._repo = attendance_repo

    async def execute(self, query: ListAttendanceQuery) -> AttendancePage:
        log.debug(
            "[attendance.list.execute] start",
            requesting_user_id=query.requesting_user.id,
            requesting_user_role=query.requesting_user.role.value,
            employee_id=query.employee_id,
            zone_id=query.zone_id,
            status=query.status.value if query.status else None,
            limit=query.limit,
            offset=query.offset,
        )

        # Self-only проверка для роли EMPLOYEE.
        effective_employee_id = self._enforce_self_only(query)

        items = await self._repo.list(
            employee_id=effective_employee_id,
            zone_id=query.zone_id,
            status=query.status,
            started_from=query.started_from,
            started_to=query.started_to,
            limit=query.limit,
            offset=query.offset,
        )
        total = await self._repo.count(
            employee_id=effective_employee_id,
            zone_id=query.zone_id,
            status=query.status,
            started_from=query.started_from,
            started_to=query.started_to,
        )

        log.info(
            "[attendance.list.execute] done",
            requesting_user_id=query.requesting_user.id,
            returned=len(items),
            total=total,
        )
        return AttendancePage(
            items=items,
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    @staticmethod
    def _enforce_self_only(query: ListAttendanceQuery) -> int | None:
        """Возвращает effective employee_id с учётом self-only правил.

        - ADMIN: возвращает query.employee_id как есть (None = все).
        - EMPLOYEE без employee_id: подставляет requesting_user.id.
        - EMPLOYEE с employee_id != requesting_user.id: ForbiddenError.
        - EMPLOYEE с employee_id == requesting_user.id: разрешено.
        """
        user = query.requesting_user
        if user.role is Role.ADMIN:
            return query.employee_id

        # role == EMPLOYEE
        if query.employee_id is None:
            return user.id
        if query.employee_id != user.id:
            log.warning(
                "[attendance.list.execute] forbidden_other_employee",
                requesting_user_id=user.id,
                requested_employee_id=query.employee_id,
            )
            raise ForbiddenError(
                code="attendance_self_only",
                message=(
                    "Сотрудник может смотреть только свои записи учёта посещаемости"
                ),
            )
        return user.id
