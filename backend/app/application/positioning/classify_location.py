"""Use case классификации местоположения по RSSI-вектору.

Lazy training: при первом запросе (если classifier не обучен)
загружает калибровочные данные через FingerprintRepository и
маппинг zone_id → ZoneType через ZoneRepository, затем тренирует
classifier. Кеш — на уровне самого classifier'а (singleton через DI).

При CRUD-операциях над калибровкой (создание/удаление) classifier
не инвалидируется автоматически — это ограничение пилота
(см. open question в плане). Для production добавим explicit
invalidate-flag или event-driven retrain.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.positioning.classifiers import PositionClassifier
from app.domain.positioning.entities import ZoneClassification
from app.domain.radiomap.repositories import FingerprintRepository
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.zones.entities import ZoneType
from app.domain.zones.repositories import ZoneRepository

log = get_logger(__name__)


@dataclass(frozen=True)
class ClassifyLocationCommand:
    """Команда классификации позиции.

    `employee_id` опциональный — на пилоте не используется в
    самой классификации, но логируется для аудита и пригодится
    на следующих вехах (учёт времени, AttendanceLog).
    """

    rssi_vector: RSSIVector
    employee_id: int | None = None


class ClassifyLocationUseCase:
    def __init__(
        self,
        fingerprint_repo: FingerprintRepository,
        zone_repo: ZoneRepository,
        classifier: PositionClassifier,
    ) -> None:
        self._fingerprint_repo = fingerprint_repo
        self._zone_repo = zone_repo
        self._classifier = classifier

    async def execute(self, cmd: ClassifyLocationCommand) -> ZoneClassification:
        log.debug(
            "[positioning.classify.execute] start",
            employee_id=cmd.employee_id,
            ap_count=len(cmd.rssi_vector),
        )

        if not self._classifier.is_trained():
            await self._train_lazily()

        result = self._classifier.classify(cmd.rssi_vector)
        log.info(
            "[positioning.classify.execute] success",
            employee_id=cmd.employee_id,
            classifier=result.classifier_name,
            zone_id=result.zone_id,
            confidence=float(result.confidence),
        )
        return result

    async def _train_lazily(self) -> None:
        """Подгружает калибровочные данные и тренирует classifier."""
        log.info("[positioning.classify.execute] training classifier (lazy)")

        calibration_set = await self._fingerprint_repo.list_calibrated_all()
        # build_feature_matrix кинет TrainingError, если выборка пуста
        # или недостаточно точек на зону. Use case не ловит — пробрасывает
        # дальше для exception handler (→ 503 classifier_not_ready).

        zone_types = await self._build_zone_types_map()
        self._classifier.train(calibration_set, zone_types)

    async def _build_zone_types_map(self) -> dict[int, ZoneType]:
        """Собирает маппинг `zone_id → ZoneType` из ZoneRepository.

        Загружаем все зоны (не пагинируем — на пилоте десятки зон).
        Если потребуется оптимизация — добавим `get_zone_types_for_ids`
        метод в ZoneRepository, который выберет только нужные.
        """
        # Берём с большим limit — реалистично < 200 зон в одном здании.
        zones = await self._zone_repo.list(limit=1000, offset=0)
        return {zone.id: zone.type for zone in zones}
