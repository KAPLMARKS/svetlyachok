"""Use case явной тренировки классификатора.

На пилоте используется внутри `ClassifyLocationUseCase` (lazy).
Отдельный use case оставляем как entry point для будущего admin-
эндпоинта (например, `POST /api/v1/positioning/retrain`), когда
понадобится вручную форсировать перетренировку после массового
обновления калибровочной выборки.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.positioning.classifiers import PositionClassifier
from app.domain.radiomap.repositories import FingerprintRepository
from app.domain.zones.entities import ZoneType
from app.domain.zones.repositories import ZoneRepository

log = get_logger(__name__)


@dataclass(frozen=True)
class TrainClassifierCommand:
    """Команда без полей — full retrain на текущей калибровочной выборке."""


@dataclass(frozen=True)
class TrainClassifierResult:
    """Метаданные о завершившемся обучении.

    Используется для возврата клиенту/admin-логирования.
    """

    calibration_size: int
    n_zones: int
    classifier_name: str | None


class TrainClassifierUseCase:
    def __init__(
        self,
        fingerprint_repo: FingerprintRepository,
        zone_repo: ZoneRepository,
        classifier: PositionClassifier,
    ) -> None:
        self._fingerprint_repo = fingerprint_repo
        self._zone_repo = zone_repo
        self._classifier = classifier

    async def execute(
        self, cmd: TrainClassifierCommand | None = None
    ) -> TrainClassifierResult:
        del cmd  # пустая команда; явно отбрасываем

        log.info("[positioning.train.execute] start")

        calibration_set = await self._fingerprint_repo.list_calibrated_all()
        zone_types = await self._build_zone_types_map()
        self._classifier.train(calibration_set, zone_types)

        n_zones = len({fp.zone_id for fp in calibration_set if fp.zone_id is not None})
        result = TrainClassifierResult(
            calibration_size=len(calibration_set),
            n_zones=n_zones,
            classifier_name=type(self._classifier).__name__,
        )
        log.info(
            "[positioning.train.execute] success",
            calibration_size=result.calibration_size,
            n_zones=result.n_zones,
            classifier_name=result.classifier_name,
        )
        return result

    async def _build_zone_types_map(self) -> dict[int, ZoneType]:
        zones = await self._zone_repo.list(limit=1000, offset=0)
        return {zone.id: zone.type for zone in zones}
