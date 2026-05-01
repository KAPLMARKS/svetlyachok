"""Use case списка сотрудников с пагинацией и фильтрами (admin-only)."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.shared import Page
from app.core.logging import get_logger
from app.domain.employees.entities import Employee, Role
from app.domain.employees.repositories import EmployeeRepository

log = get_logger(__name__)

# Лимит на размер страницы. Выше — клиент должен переходить к следующей.
# Защищает от случайного DoS через `?limit=1000000`.
_MAX_LIMIT = 200


@dataclass(frozen=True)
class ListEmployeesQuery:
    role: Role | None = None
    is_active: bool | None = None
    limit: int = 50
    offset: int = 0


class ListEmployeesUseCase:
    def __init__(self, employee_repo: EmployeeRepository) -> None:
        self._repo = employee_repo

    async def execute(self, query: ListEmployeesQuery) -> Page[Employee]:
        # Сжимаем лимит/смещение в безопасный диапазон. Pydantic
        # должен это уже сделать, но повторная проверка — invariant.
        limit = max(1, min(query.limit, _MAX_LIMIT))
        offset = max(0, query.offset)

        log.debug(
            "[employees.list.execute] start",
            role=query.role.value if query.role else None,
            is_active=query.is_active,
            limit=limit,
            offset=offset,
        )

        items = await self._repo.list(
            role=query.role,
            is_active=query.is_active,
            limit=limit,
            offset=offset,
        )
        total = await self._repo.count(role=query.role, is_active=query.is_active)

        log.debug(
            "[employees.list.execute] done",
            total=total,
            returned=len(items),
        )
        return Page(items=items, total=total, limit=limit, offset=offset)
