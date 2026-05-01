"""Use case обновления зоны (admin-only)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.shared.exceptions import ConflictError, NotFoundError
from app.domain.zones.entities import Zone, ZoneType
from app.domain.zones.repositories import ZoneRepository

log = get_logger(__name__)


@dataclass(frozen=True)
class UpdateZoneCommand:
    zone_id: int
    name: str | None = None
    type: ZoneType | None = None
    description: str | None = None
    display_color: str | None = None
    # Явные флаги для очистки опциональных полей; None в description/
    # display_color означает «не менять».
    clear_description: bool = False
    clear_display_color: bool = False


class UpdateZoneUseCase:
    def __init__(self, zone_repo: ZoneRepository) -> None:
        self._repo = zone_repo

    async def execute(self, cmd: UpdateZoneCommand) -> Zone:
        log.debug("[zones.update.execute] start", zone_id=cmd.zone_id)

        existing = await self._repo.get_by_id(cmd.zone_id)
        if existing is None:
            log.warning(
                "[zones.update.execute] fail",
                reason="not_found",
                zone_id=cmd.zone_id,
            )
            raise NotFoundError(
                code="zone_not_found",
                message=f"Зона с id={cmd.zone_id} не найдена",
            )

        # Проверка уникальности name на уровне application — быстрый
        # ответ; race condition закрывается unique-constraint в БД.
        if cmd.name is not None and cmd.name != existing.name:
            duplicate = await self._repo.get_by_name(cmd.name)
            if duplicate is not None and duplicate.id != cmd.zone_id:
                log.warning(
                    "[zones.update.execute] fail",
                    reason="name_taken",
                    name=cmd.name,
                )
                raise ConflictError(
                    code="zone_name_taken",
                    message=f"Зона с именем {cmd.name!r} уже существует",
                )

        updated = existing.with_changes(
            name=cmd.name,
            type=cmd.type,
            description=cmd.description,
            display_color=cmd.display_color,
            clear_description=cmd.clear_description,
            clear_display_color=cmd.clear_display_color,
        )
        result = await self._repo.update(updated)

        log.info("[zones.update.execute] success", zone_id=result.id)
        return result
