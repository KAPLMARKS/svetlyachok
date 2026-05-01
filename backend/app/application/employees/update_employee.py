"""Use case обновления сотрудника (PATCH-семантика).

Все поля команды опциональны: None означает «не менять». Use case
применяет только non-None поля к существующему Employee и сохраняет.

Авторизация (admin / self с ограниченным набором полей) — на уровне
endpoint'а, не здесь. Use case принимает то, что пришло, и обновляет
домен; presentation слой отбрасывает поля, которых self не имеет права менять.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import time

from app.core.logging import get_logger
from app.domain.employees.entities import Employee, Role
from app.domain.employees.repositories import EmployeeRepository
from app.domain.shared.exceptions import NotFoundError

log = get_logger(__name__)


@dataclass(frozen=True)
class UpdateEmployeeCommand:
    employee_id: int
    full_name: str | None = None
    role: Role | None = None
    schedule_start: time | None = None
    schedule_end: time | None = None
    # Явные флаги «очистить расписание» — None в schedule_start/_end
    # означает «не менять», а не «убрать».
    clear_schedule_start: bool = False
    clear_schedule_end: bool = False


class UpdateEmployeeUseCase:
    def __init__(self, employee_repo: EmployeeRepository) -> None:
        self._repo = employee_repo

    async def execute(self, cmd: UpdateEmployeeCommand) -> Employee:
        log.debug("[employees.update.execute] start", employee_id=cmd.employee_id)

        existing = await self._repo.get_by_id(cmd.employee_id)
        if existing is None:
            log.warning(
                "[employees.update.execute] fail",
                reason="not_found",
                employee_id=cmd.employee_id,
            )
            raise NotFoundError(
                code="employee_not_found",
                message=f"Сотрудник с id={cmd.employee_id} не найден",
            )

        new_schedule_start = (
            None
            if cmd.clear_schedule_start
            else (
                cmd.schedule_start
                if cmd.schedule_start is not None
                else existing.schedule_start
            )
        )
        new_schedule_end = (
            None
            if cmd.clear_schedule_end
            else (
                cmd.schedule_end
                if cmd.schedule_end is not None
                else existing.schedule_end
            )
        )

        updated = replace(
            existing,
            full_name=cmd.full_name if cmd.full_name is not None else existing.full_name,
            role=cmd.role if cmd.role is not None else existing.role,
            schedule_start=new_schedule_start,
            schedule_end=new_schedule_end,
        )

        result = await self._repo.update(updated)

        log.info(
            "[employees.update.execute] success",
            employee_id=result.id,
            changed_full_name=cmd.full_name is not None,
            changed_role=cmd.role is not None,
            changed_schedule=cmd.schedule_start is not None
            or cmd.schedule_end is not None
            or cmd.clear_schedule_start
            or cmd.clear_schedule_end,
        )
        return result
