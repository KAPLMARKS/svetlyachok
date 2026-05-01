"""SQLAlchemy-реализация EmployeeRepository.

Маппит ORM-модель `EmployeeORM` в доменную `Employee`. Никогда не
возвращает ORM-объект наружу — это правило Clean Architecture
(use cases работают только с domain-сущностями).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.employees.entities import Employee, Role
from app.domain.employees.repositories import EmployeeRepository
from app.infrastructure.db.orm.employees import Employee as EmployeeORM
from app.infrastructure.db.orm.employees import Role as OrmRole

log = get_logger(__name__)


class SqlAlchemyEmployeeRepository(EmployeeRepository):
    """Async-репозиторий сотрудников на SQLAlchemy 2.x."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, employee_id: int) -> Employee | None:
        log.debug("[employees.repo.get_by_id] start", id=employee_id)
        stmt = select(EmployeeORM).where(EmployeeORM.id == employee_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        result = self._to_domain(orm) if orm is not None else None
        log.debug("[employees.repo.get_by_id] done", id=employee_id, found=result is not None)
        return result

    async def get_by_email(self, email: str) -> Employee | None:
        log.debug("[employees.repo.get_by_email] start", email=email)
        stmt = select(EmployeeORM).where(EmployeeORM.email == email)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        result = self._to_domain(orm) if orm is not None else None
        log.debug(
            "[employees.repo.get_by_email] done",
            email=email,
            found=result is not None,
        )
        return result

    @staticmethod
    def _to_domain(orm: EmployeeORM) -> Employee:
        """Маппер ORM → domain.

        Конвертирует ORM RoleEnum в domain Role (значения совпадают —
        проверено в orm/employees.py и domain/employees/entities.py).
        """
        return Employee(
            id=orm.id,
            email=orm.email,
            full_name=orm.full_name,
            role=_map_role(orm.role),
            hashed_password=orm.hashed_password,
            is_active=orm.is_active,
            schedule_start=orm.schedule_start,
            schedule_end=orm.schedule_end,
        )


def _map_role(orm_role: OrmRole) -> Role:
    """ORM Role → domain Role.

    Значения enum'ов гарантированно совпадают (admin/employee), но
    делаем явный маппинг — на случай, если в будущем расходятся
    (например, в БД появится больше ролей, чем в domain).
    """
    return Role(orm_role.value)
