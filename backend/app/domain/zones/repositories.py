"""Контракт репозитория зон.

Use cases (`application/zones/`) работают через этот Protocol,
не зная о SQLAlchemy. Реализация — в
`infrastructure/repositories/zones_repository.py`.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.zones.entities import Zone, ZoneType


class ZoneRepository(Protocol):
    """Контракт хранилища зон. Не зависит от SQLAlchemy."""

    async def get_by_id(self, zone_id: int) -> Zone | None:
        """Возвращает Zone или None, если не найдена."""
        ...

    async def get_by_name(self, name: str) -> Zone | None:
        """Возвращает Zone по уникальному name или None."""
        ...

    async def list(
        self,
        *,
        type_filter: ZoneType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Zone]:
        """Возвращает страницу зон. Сортировка — по id ASC."""
        ...

    async def count(self, *, type_filter: ZoneType | None = None) -> int:
        """Общее количество зон по тем же фильтрам, что и list."""
        ...

    async def add(self, zone: Zone) -> Zone:
        """Создаёт новую зону. При нарушении unique-constraint на name —
        `ConflictError(code="zone_name_taken")`."""
        ...

    async def update(self, zone: Zone) -> Zone:
        """Обновляет зону по id. NotFound → `NotFoundError(zone_not_found)`."""
        ...

    async def delete_by_id(self, zone_id: int) -> bool:
        """Удаляет зону по id.

        Возвращает True если удалили, False если зона не найдена.
        Если зона связана с attendance_logs (FK ondelete=RESTRICT) —
        реализация поднимает `ConflictError(code="zone_in_use")`.
        """
        ...
