"""Use cases списка и просмотра зон (доступны любому авторизованному).

Клиенты (mobile/web) запрашивают список для UI — например, для
отображения карты помещений, выбора зоны при ручной калибровке и т.д.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.shared import Page
from app.core.logging import get_logger
from app.domain.shared.exceptions import NotFoundError
from app.domain.zones.entities import Zone, ZoneType
from app.domain.zones.repositories import ZoneRepository

log = get_logger(__name__)

_MAX_LIMIT = 200


@dataclass(frozen=True)
class ListZonesQuery:
    type_filter: ZoneType | None = None
    limit: int = 50
    offset: int = 0


class ListZonesUseCase:
    def __init__(self, zone_repo: ZoneRepository) -> None:
        self._repo = zone_repo

    async def execute(self, query: ListZonesQuery) -> Page[Zone]:
        limit = max(1, min(query.limit, _MAX_LIMIT))
        offset = max(0, query.offset)

        log.debug(
            "[zones.list.execute] start",
            type_filter=query.type_filter.value if query.type_filter else None,
            limit=limit,
            offset=offset,
        )

        items = await self._repo.list(
            type_filter=query.type_filter,
            limit=limit,
            offset=offset,
        )
        total = await self._repo.count(type_filter=query.type_filter)

        log.debug(
            "[zones.list.execute] done", total=total, returned=len(items)
        )
        return Page(items=items, total=total, limit=limit, offset=offset)


@dataclass(frozen=True)
class GetZoneQuery:
    zone_id: int


class GetZoneUseCase:
    def __init__(self, zone_repo: ZoneRepository) -> None:
        self._repo = zone_repo

    async def execute(self, query: GetZoneQuery) -> Zone:
        log.debug("[zones.get.execute] start", zone_id=query.zone_id)
        zone = await self._repo.get_by_id(query.zone_id)
        if zone is None:
            log.warning(
                "[zones.get.execute] fail", reason="not_found", zone_id=query.zone_id
            )
            raise NotFoundError(
                code="zone_not_found",
                message=f"Зона с id={query.zone_id} не найдена",
            )
        log.debug("[zones.get.execute] done", zone_id=zone.id)
        return zone
