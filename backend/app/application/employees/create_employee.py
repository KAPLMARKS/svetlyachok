"""Use case создания сотрудника (admin-only).

Admin указывает email, full_name, роль и временный пароль. Use case
проверяет уникальность email на уровне application (быстрая reaction
до похода в БД), хеширует пароль и сохраняет.

Дублирующая защита от race condition — на уровне репозитория через
unique-constraint и обработку IntegrityError → ConflictError. Pre-check
здесь не идеален (TOCTOU), но даёт читаемый ответ в 99% случаев.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from app.core.logging import get_logger
from app.domain.employees.entities import Employee, Role
from app.domain.employees.repositories import EmployeeRepository
from app.domain.employees.services import PasswordHasher
from app.domain.shared.exceptions import ConflictError

log = get_logger(__name__)


@dataclass(frozen=True)
class CreateEmployeeCommand:
    email: str
    full_name: str
    role: Role
    initial_password: str
    schedule_start: time | None = None
    schedule_end: time | None = None


class CreateEmployeeUseCase:
    def __init__(
        self,
        employee_repo: EmployeeRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._repo = employee_repo
        self._hasher = password_hasher

    async def execute(self, cmd: CreateEmployeeCommand) -> Employee:
        log.debug(
            "[employees.create.execute] start",
            email=cmd.email,
            role=cmd.role.value,
        )

        existing = await self._repo.get_by_email(cmd.email)
        if existing is not None:
            log.warning(
                "[employees.create.execute] fail",
                reason="email_taken",
                email=cmd.email,
            )
            raise ConflictError(
                code="employee_email_taken",
                message=f"Сотрудник с email {cmd.email!r} уже существует",
            )

        hashed = self._hasher.hash(cmd.initial_password)
        # id=0 — placeholder, репозиторий установит реальный после INSERT.
        new_employee = Employee(
            id=0,
            email=cmd.email,
            full_name=cmd.full_name,
            role=cmd.role,
            hashed_password=hashed,
            is_active=True,
            schedule_start=cmd.schedule_start,
            schedule_end=cmd.schedule_end,
        )
        created = await self._repo.add(new_employee)

        log.info(
            "[employees.create.execute] success",
            employee_id=created.id,
            email=created.email,
            role=created.role.value,
        )
        return created
