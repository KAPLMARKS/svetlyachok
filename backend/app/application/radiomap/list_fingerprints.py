"""Use cases просмотра отпечатков (admin)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.shared import Page
from app.core.logging import get_logger
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.repositories import FingerprintRepository
from app.domain.shared.exceptions import NotFoundError

log = get_logger(__name__)

_MAX_LIMIT = 200


@dataclass(frozen=True)
class ListFingerprintsQuery:
    employee_id: int | None = None
    zone_id: int | None = None
    is_calibration: bool | None = None
    captured_from: datetime | None = None
    captured_to: datetime | None = None
    limit: int = 50
    offset: int = 0


class ListFingerprintsUseCase:
    def __init__(self, fingerprint_repo: FingerprintRepository) -> None:
        self._repo = fingerprint_repo

    async def execute(self, query: ListFingerprintsQuery) -> Page[Fingerprint]:
        limit = max(1, min(query.limit, _MAX_LIMIT))
        offset = max(0, query.offset)

        log.debug(
            "[radiomap.list.execute] start",
            employee_id=query.employee_id,
            zone_id=query.zone_id,
            is_calibration=query.is_calibration,
            limit=limit,
            offset=offset,
        )

        items = await self._repo.list(
            employee_id=query.employee_id,
            zone_id=query.zone_id,
            is_calibration=query.is_calibration,
            captured_from=query.captured_from,
            captured_to=query.captured_to,
            limit=limit,
            offset=offset,
        )
        total = await self._repo.count(
            employee_id=query.employee_id,
            zone_id=query.zone_id,
            is_calibration=query.is_calibration,
            captured_from=query.captured_from,
            captured_to=query.captured_to,
        )
        log.debug("[radiomap.list.execute] done", total=total, returned=len(items))
        return Page(items=items, total=total, limit=limit, offset=offset)


@dataclass(frozen=True)
class GetFingerprintQuery:
    fingerprint_id: int


class GetFingerprintUseCase:
    def __init__(self, fingerprint_repo: FingerprintRepository) -> None:
        self._repo = fingerprint_repo

    async def execute(self, query: GetFingerprintQuery) -> Fingerprint:
        log.debug(
            "[radiomap.get.execute] start", fingerprint_id=query.fingerprint_id
        )
        fp = await self._repo.get_by_id(query.fingerprint_id)
        if fp is None:
            log.warning(
                "[radiomap.get.execute] fail",
                reason="not_found",
                fingerprint_id=query.fingerprint_id,
            )
            raise NotFoundError(
                code="fingerprint_not_found",
                message=f"Отпечаток с id={query.fingerprint_id} не найден",
            )
        log.debug("[radiomap.get.execute] done", fingerprint_id=fp.id)
        return fp
