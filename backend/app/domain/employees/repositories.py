"""Контракт репозитория сотрудников.

Use cases (`application/employees/`) работают через этот Protocol,
не зная о SQLAlchemy. Реализация — в
`infrastructure/repositories/employees_repository.py`.

Тестируется на in-memory fake — см. `tests/unit/application/`.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.employees.entities import Employee


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
