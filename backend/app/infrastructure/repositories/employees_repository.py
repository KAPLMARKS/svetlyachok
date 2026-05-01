"""SQLAlchemy-реализация EmployeeRepository.

Маппит ORM-модель `EmployeeORM` в доменную `Employee`. Никогда не
возвращает ORM-объект наружу — это правило Clean Architecture
(use cases работают только с domain-сущностями).
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.employees.entities import Employee, Role
from app.domain.employees.repositories import EmployeeRepository
from app.domain.shared.exceptions import ConflictError, NotFoundError
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

    async def list(
        self,
        *,
        role: Role | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Employee]:
        log.debug(
            "[employees.repo.list] start",
            role=role.value if role else None,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )
        stmt = select(EmployeeORM).order_by(EmployeeORM.id.asc())
        stmt = self._apply_filters(stmt, role=role, is_active=is_active)
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        result = [self._to_domain(orm) for orm in rows]
        log.debug("[employees.repo.list] done", returned=len(result))
        return result

    async def count(
        self,
        *,
        role: Role | None = None,
        is_active: bool | None = None,
    ) -> int:
        log.debug(
            "[employees.repo.count] start",
            role=role.value if role else None,
            is_active=is_active,
        )
        stmt = select(func.count()).select_from(EmployeeORM)
        stmt = self._apply_filters(stmt, role=role, is_active=is_active)
        total = (await self._session.execute(stmt)).scalar_one()
        log.debug("[employees.repo.count] done", total=total)
        return int(total)

    async def add(self, employee: Employee) -> Employee:
        log.debug("[employees.repo.add] start", email=employee.email)
        orm = EmployeeORM(
            email=employee.email,
            full_name=employee.full_name,
            role=OrmRole(employee.role.value),
            hashed_password=employee.hashed_password,
            is_active=employee.is_active,
            schedule_start=employee.schedule_start,
            schedule_end=employee.schedule_end,
        )
        self._session.add(orm)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            log.warning(
                "[employees.repo.add] conflict",
                email=employee.email,
                exc_type=type(exc).__name__,
            )
            raise ConflictError(
                code="employee_email_taken",
                message=f"Сотрудник с email {employee.email!r} уже существует",
            ) from exc

        await self._session.refresh(orm)
        result = self._to_domain(orm)
        log.info("[employees.repo.add] done", employee_id=result.id, email=result.email)
        return result

    async def update(self, employee: Employee) -> Employee:
        log.debug("[employees.repo.update] start", id=employee.id)
        stmt = select(EmployeeORM).where(EmployeeORM.id == employee.id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            log.warning("[employees.repo.update] not_found", id=employee.id)
            raise NotFoundError(
                code="employee_not_found",
                message=f"Сотрудник с id={employee.id} не найден",
            )

        orm.email = employee.email
        orm.full_name = employee.full_name
        orm.role = OrmRole(employee.role.value)
        orm.hashed_password = employee.hashed_password
        orm.is_active = employee.is_active
        orm.schedule_start = employee.schedule_start
        orm.schedule_end = employee.schedule_end

        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            log.warning(
                "[employees.repo.update] conflict",
                id=employee.id,
                exc_type=type(exc).__name__,
            )
            raise ConflictError(
                code="employee_email_taken",
                message=f"Сотрудник с email {employee.email!r} уже существует",
            ) from exc

        await self._session.refresh(orm)
        result = self._to_domain(orm)
        log.info("[employees.repo.update] done", employee_id=result.id)
        return result

    @staticmethod
    def _apply_filters(stmt, *, role: Role | None, is_active: bool | None):
        if role is not None:
            stmt = stmt.where(EmployeeORM.role == OrmRole(role.value))
        if is_active is not None:
            stmt = stmt.where(EmployeeORM.is_active == is_active)
        return stmt

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
