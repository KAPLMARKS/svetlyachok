"""Use case списка калибровочных точек (любой авторизованный).

Под капотом — обычный list по фингерпринтам с принудительным
`is_calibration=True`. Отдельный use case оставляет API чистым: клиенту
не нужно знать про is_calibration-флаг.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.shared import Page
from app.core.logging import get_logger
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.repositories import FingerprintRepository

log = get_logger(__name__)

_MAX_LIMIT = 200


@dataclass(frozen=True)
class ListCalibrationPointsQuery:
    zone_id: int | None = None
    limit: int = 50
    offset: int = 0


class ListCalibrationPointsUseCase:
    def __init__(self, fingerprint_repo: FingerprintRepository) -> None:
        self._repo = fingerprint_repo

    async def execute(self, query: ListCalibrationPointsQuery) -> Page[Fingerprint]:
        limit = max(1, min(query.limit, _MAX_LIMIT))
        offset = max(0, query.offset)

        log.debug(
            "[radiomap.list_calibration.execute] start",
            zone_id=query.zone_id,
            limit=limit,
            offset=offset,
        )

        items = await self._repo.list(
            zone_id=query.zone_id,
            is_calibration=True,
            limit=limit,
            offset=offset,
        )
        total = await self._repo.count(
            zone_id=query.zone_id,
            is_calibration=True,
        )
        log.debug(
            "[radiomap.list_calibration.execute] done",
            total=total,
            returned=len(items),
        )
        return Page(items=items, total=total, limit=limit, offset=offset)
