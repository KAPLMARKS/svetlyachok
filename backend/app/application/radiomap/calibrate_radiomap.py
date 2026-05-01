"""Use case создания калибровочной точки (admin).

Калибровочная точка — эталонный RSSI-отпечаток, привязанный к конкретной
зоне. Используется ML-классификатором как обучающая выборка.

Перед сохранением проверяем существование zone_id через ZoneRepository —
ловим ошибку рано (до IntegrityError на FK).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.logging import get_logger
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.repositories import FingerprintRepository
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.shared.exceptions import NotFoundError
from app.domain.zones.repositories import ZoneRepository

log = get_logger(__name__)


@dataclass(frozen=True)
class CreateCalibrationPointCommand:
    zone_id: int
    captured_at: datetime
    rssi_vector: RSSIVector
    sample_count: int = 1
    device_id: str | None = None
    employee_id: int | None = None


class CreateCalibrationPointUseCase:
    def __init__(
        self,
        fingerprint_repo: FingerprintRepository,
        zone_repo: ZoneRepository,
    ) -> None:
        self._fingerprint_repo = fingerprint_repo
        self._zone_repo = zone_repo

    async def execute(self, cmd: CreateCalibrationPointCommand) -> Fingerprint:
        log.debug(
            "[radiomap.calibrate.execute] start",
            zone_id=cmd.zone_id,
            ap_count=len(cmd.rssi_vector),
        )

        zone = await self._zone_repo.get_by_id(cmd.zone_id)
        if zone is None:
            log.warning(
                "[radiomap.calibrate.execute] fail",
                reason="zone_not_found",
                zone_id=cmd.zone_id,
            )
            raise NotFoundError(
                code="zone_not_found",
                message=f"Зона с id={cmd.zone_id} не найдена",
            )

        fingerprint = Fingerprint(
            id=0,
            employee_id=cmd.employee_id,
            zone_id=cmd.zone_id,
            is_calibration=True,
            captured_at=cmd.captured_at,
            device_id=cmd.device_id,
            rssi_vector=cmd.rssi_vector,
            sample_count=cmd.sample_count,
        )
        created = await self._fingerprint_repo.add(fingerprint)

        log.info(
            "[radiomap.calibrate.execute] success",
            fingerprint_id=created.id,
            zone_id=created.zone_id,
            zone_name=zone.name,
            ap_count=len(cmd.rssi_vector),
        )
        return created
