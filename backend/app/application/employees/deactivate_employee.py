"""Use cases смены `is_active`-флага сотрудника (soft-delete и активация).

Anti-self-lock: admin не может деактивировать свою собственную учётку,
иначе мог бы заблокировать всю систему. Принудительный путь —
непосредственный SQL или другой admin.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.employees.entities import Employee
from app.domain.employees.repositories import EmployeeRepository
from app.domain.shared.exceptions import ForbiddenError, NotFoundError

log = get_logger(__name__)


@dataclass(frozen=True)
class DeactivateEmployeeCommand:
    employee_id: int
    current_user_id: int


@dataclass(frozen=True)
class ActivateEmployeeCommand:
    employee_id: int


class DeactivateEmployeeUseCase:
    def __init__(self, employee_repo: EmployeeRepository) -> None:
        self._repo = employee_repo

    async def execute(self, cmd: DeactivateEmployeeCommand) -> Employee:
        log.debug(
            "[employees.deactivate.execute] start",
            employee_id=cmd.employee_id,
            current_user_id=cmd.current_user_id,
        )

        if cmd.employee_id == cmd.current_user_id:
            log.warning(
                "[employees.deactivate.execute] fail",
                reason="self_deactivation",
                employee_id=cmd.employee_id,
            )
            raise ForbiddenError(
                code="cannot_deactivate_self",
                message=(
                    "Нельзя деактивировать свою собственную учётную запись. "
                    "Попросите другого администратора."
                ),
            )

        existing = await self._repo.get_by_id(cmd.employee_id)
        if existing is None:
            raise NotFoundError(
                code="employee_not_found",
                message=f"Сотрудник с id={cmd.employee_id} не найден",
            )

        if not existing.is_active:
            # Идемпотентность: вызов на уже неактивного — ОК, без update.
            log.debug(
                "[employees.deactivate.execute] already_inactive",
                employee_id=cmd.employee_id,
            )
            return existing

        updated = existing.with_is_active(False)
        result = await self._repo.update(updated)
        log.info(
            "[employees.deactivate.execute] success",
            employee_id=result.id,
            is_active=False,
        )
        return result


class ActivateEmployeeUseCase:
    def __init__(self, employee_repo: EmployeeRepository) -> None:
        self._repo = employee_repo

    async def execute(self, cmd: ActivateEmployeeCommand) -> Employee:
        log.debug(
            "[employees.activate.execute] start", employee_id=cmd.employee_id
        )

        existing = await self._repo.get_by_id(cmd.employee_id)
        if existing is None:
            raise NotFoundError(
                code="employee_not_found",
                message=f"Сотрудник с id={cmd.employee_id} не найден",
            )

        if existing.is_active:
            log.debug(
                "[employees.activate.execute] already_active",
                employee_id=cmd.employee_id,
            )
            return existing

        updated = existing.with_is_active(True)
        result = await self._repo.update(updated)
        log.info(
            "[employees.activate.execute] success",
            employee_id=result.id,
            is_active=True,
        )
        return result
