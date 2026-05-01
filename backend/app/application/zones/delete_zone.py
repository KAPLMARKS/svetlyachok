"""Use case удаления зоны (admin-only).

Hard-delete: если зона связана с attendance_logs (FK ondelete=RESTRICT),
репозиторий поднимает ConflictError(zone_in_use). Soft-delete не
делаем — на пилоте не критично, добавим позже через `archived_at`
если потребуется.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.shared.exceptions import NotFoundError
from app.domain.zones.repositories import ZoneRepository

log = get_logger(__name__)


@dataclass(frozen=True)
class DeleteZoneCommand:
    zone_id: int


class DeleteZoneUseCase:
    def __init__(self, zone_repo: ZoneRepository) -> None:
        self._repo = zone_repo

    async def execute(self, cmd: DeleteZoneCommand) -> None:
        log.debug("[zones.delete.execute] start", zone_id=cmd.zone_id)

        # delete_by_id сам поднимет ConflictError(zone_in_use) при FK
        # RESTRICT-нарушении — пробрасываем дальше.
        deleted = await self._repo.delete_by_id(cmd.zone_id)
        if not deleted:
            log.warning(
                "[zones.delete.execute] fail",
                reason="not_found",
                zone_id=cmd.zone_id,
            )
            raise NotFoundError(
                code="zone_not_found",
                message=f"Зона с id={cmd.zone_id} не найдена",
            )

        log.info("[zones.delete.execute] success", zone_id=cmd.zone_id)
