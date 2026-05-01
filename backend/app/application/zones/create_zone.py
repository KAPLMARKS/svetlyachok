"""Use case создания зоны (admin-only)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.shared.exceptions import ConflictError
from app.domain.zones.entities import Zone, ZoneType
from app.domain.zones.repositories import ZoneRepository

log = get_logger(__name__)


@dataclass(frozen=True)
class CreateZoneCommand:
    name: str
    type: ZoneType
    description: str | None = None
    display_color: str | None = None


class CreateZoneUseCase:
    def __init__(self, zone_repo: ZoneRepository) -> None:
        self._repo = zone_repo

    async def execute(self, cmd: CreateZoneCommand) -> Zone:
        log.debug(
            "[zones.create.execute] start", name=cmd.name, type=cmd.type.value
        )

        existing = await self._repo.get_by_name(cmd.name)
        if existing is not None:
            log.warning(
                "[zones.create.execute] fail", reason="name_taken", name=cmd.name
            )
            raise ConflictError(
                code="zone_name_taken",
                message=f"Зона с именем {cmd.name!r} уже существует",
            )

        zone = Zone(
            id=0,
            name=cmd.name,
            type=cmd.type,
            description=cmd.description,
            display_color=cmd.display_color,
        )
        created = await self._repo.add(zone)

        log.info(
            "[zones.create.execute] success",
            zone_id=created.id,
            name=created.name,
            type=created.type.value,
        )
        return created
