"""Контракт репозитория сотрудников.

Use cases (`application/employees/`) работают через этот Protocol,
не зная о SQLAlchemy. Реализация — в
`infrastructure/repositories/employees_repository.py`.

Тестируется на in-memory fake — см. `tests/unit/application/`.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.employees.entities import Employee, Role


class EmployeeRepository(Protocol):
    """Контракт хранилища сотрудников. Не зависит от SQLAlchemy."""

    async def get_by_id(self, employee_id: int) -> Employee | None:
        """Возвращает Employee или None, если не найден."""
        ...

    async def get_by_email(self, email: str) -> Employee | None:
        """Возвращает Employee по email или None.

        Email сравнивается case-sensitive — в реализации используем
        unique constraint и raw equality. Если потребуется
        case-insensitive (RFC 5321 разрешает разный case в local-part),
        добавим citext-расширение и отдельную миграцию.
        """
        ...

    async def list(
        self,
        *,
        role: Role | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Employee]:
        """Возвращает страницу сотрудников по фильтрам.

        Фильтры комбинируются через AND. None означает «не фильтровать».
        Сортировка — по id ASC (стабильная). limit/offset для пагинации.
        """
        ...

    async def count(
        self,
        *,
        role: Role | None = None,
        is_active: bool | None = None,
    ) -> int:
        """Общее количество сотрудников по тем же фильтрам, что и list.

        Используется для отдачи `total` клиенту в Page-ответе.
        """
        ...

    async def add(self, employee: Employee) -> Employee:
        """Создаёт нового сотрудника. Возвращает Employee с заполненным id.

        При нарушении unique-constraint на email реализация поднимает
        `ConflictError(code="employee_email_taken")`.
        """
        ...

    async def update(self, employee: Employee) -> Employee:
        """Обновляет сотрудника по id. Возвращает обновлённую сущность.

        Если сотрудник с таким id не существует — поднимает
        `NotFoundError(code="employee_not_found")`.
        """
        ...
