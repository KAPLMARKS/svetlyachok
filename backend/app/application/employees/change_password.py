"""Use case смены пароля сотрудника.

Два режима, выбираются флагом `is_admin_reset`:

- **Admin reset** (`is_admin_reset=True`): admin сбрасывает пароль
  любому сотруднику без знания старого. Старый пароль не передаётся.
- **Self change** (`is_admin_reset=False`): сотрудник меняет свой
  собственный пароль. Обязан передать старый — verify через хешер;
  при несовпадении → UnauthorizedError(wrong_old_password).

Авторизация (кто имеет право вызывать какой режим) — на уровне
endpoint'а через require_role и self-check.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.employees.entities import Employee
from app.domain.employees.repositories import EmployeeRepository
from app.domain.employees.services import PasswordHasher
from app.domain.shared.exceptions import (
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)

log = get_logger(__name__)


@dataclass(frozen=True)
class ChangePasswordCommand:
    employee_id: int
    new_password: str
    old_password: str | None = None
    is_admin_reset: bool = False


class ChangePasswordUseCase:
    def __init__(
        self,
        employee_repo: EmployeeRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._repo = employee_repo
        self._hasher = password_hasher

    async def execute(self, cmd: ChangePasswordCommand) -> Employee:
        log.debug(
            "[employees.change_password.execute] start",
            employee_id=cmd.employee_id,
            mode="admin_reset" if cmd.is_admin_reset else "self_change",
        )

        if not cmd.is_admin_reset and cmd.old_password is None:
            # Защитная проверка — endpoint должен был это поймать раньше.
            raise ValidationError(
                code="old_password_required",
                message="Для смены своего пароля требуется указать старый",
            )

        existing = await self._repo.get_by_id(cmd.employee_id)
        if existing is None:
            log.warning(
                "[employees.change_password.execute] fail",
                reason="not_found",
                employee_id=cmd.employee_id,
            )
            raise NotFoundError(
                code="employee_not_found",
                message=f"Сотрудник с id={cmd.employee_id} не найден",
            )

        if not cmd.is_admin_reset:
            # cmd.old_password is not None — проверено выше
            assert cmd.old_password is not None
            if not self._hasher.verify(cmd.old_password, existing.hashed_password):
                log.warning(
                    "[employees.change_password.execute] fail",
                    reason="wrong_old_password",
                    employee_id=cmd.employee_id,
                )
                raise UnauthorizedError(
                    code="wrong_old_password",
                    message="Старый пароль указан неверно",
                )

        new_hashed = self._hasher.hash(cmd.new_password)
        updated = existing.with_password(new_hashed)
        result = await self._repo.update(updated)

        log.info(
            "[employees.change_password.execute] success",
            employee_id=result.id,
            mode="admin_reset" if cmd.is_admin_reset else "self_change",
        )
        return result
