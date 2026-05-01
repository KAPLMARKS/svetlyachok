"""WKNN-классификатор: KNeighborsClassifier с distance-weighting.

«W» в WKNN = `weights="distance"` — соседи влияют на голосование
обратно пропорционально расстоянию (ближе → больше вес).
НЕ путать с обычным KNN, где `weights="uniform"`.

Реализация — обёртка над `sklearn.neighbors.KNeighborsClassifier`.
Стейтфул: после `train()` хранит обученную модель и `bssid_index`.
"""

from __future__ import annotations

import numpy as np
from sklearn.neighbors import KNeighborsClassifier

from app.core.logging import get_logger
from app.domain.positioning.classifiers import PositionClassifier, TrainingError
from app.domain.positioning.entities import ZoneClassification
from app.domain.positioning.value_objects import Confidence
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import BSSID, RSSIVector
from app.domain.zones.entities import ZoneType
from app.infrastructure.ml.config import WknnConfig
from app.infrastructure.ml.features import (
    build_feature_matrix,
    build_observation_vector,
)

log = get_logger(__name__)


class WknnClassifier(PositionClassifier):
    """Weighted K-Nearest Neighbors classifier для indoor positioning."""

    def __init__(self, config: WknnConfig | None = None) -> None:
        self._config = config or WknnConfig()
        self._clf: KNeighborsClassifier | None = None
        self._bssid_index: list[BSSID] | None = None
        self._zone_types: dict[int, ZoneType] = {}

    def is_trained(self) -> bool:
        return self._clf is not None and self._bssid_index is not None

    def train(
        self,
        calibration_set: list[Fingerprint],
        zone_types: dict[int, ZoneType],
    ) -> None:
        log.info(
            "[ml.wknn.train] start",
            calibration_size=len(calibration_set),
            n_neighbors=self._config.n_neighbors,
            metric=self._config.metric,
        )

        X, y, bssid_index = build_feature_matrix(calibration_set)

        # Validate — все zone_id должны иметь ZoneType-маппинг.
        # Иначе classify не сможет вернуть полный ZoneClassification.
        unique_zones = {int(zid) for zid in y}
        missing_types = unique_zones - zone_types.keys()
        if missing_types:
            raise TrainingError(
                code="missing_zone_types",
                message=(
                    f"Не указан ZoneType для зон {sorted(missing_types)}. "
                    "Use case должен загрузить все зоны через ZoneRepository."
                ),
            )

        # KNeighborsClassifier требует n_samples >= n_neighbors.
        if len(X) < self._config.n_neighbors:
            raise TrainingError(
                code="insufficient_calibration_points",
                message=(
                    f"Калибровочных точек {len(X)}, "
                    f"требуется минимум {self._config.n_neighbors} (n_neighbors)"
                ),
            )

        clf = KNeighborsClassifier(
            n_neighbors=self._config.n_neighbors,
            weights=self._config.weights,
            metric=self._config.metric,
        )
        clf.fit(X, y)

        self._clf = clf
        self._bssid_index = bssid_index
        self._zone_types = zone_types

        log.info(
            "[ml.wknn.train] done",
            n_samples=len(X),
            n_features=int(X.shape[1]),
            n_zones=len(unique_zones),
        )

    def classify(self, observation: RSSIVector) -> ZoneClassification:
        if not self.is_trained():
            raise TrainingError(
                code="not_trained",
                message="WknnClassifier не обучен. Вызовите train() перед classify().",
            )

        # Type-narrowing для mypy.
        assert self._clf is not None
        assert self._bssid_index is not None

        vec = build_observation_vector(observation, self._bssid_index)
        predicted = int(self._clf.predict(vec)[0])
        proba = self._clf.predict_proba(vec)[0]
        confidence_value = float(np.max(proba))

        zone_type = self._zone_types.get(predicted)
        if zone_type is None:
            # Защитная проверка: предсказан zone_id, для которого нет
            # маппинга. Не должно случаться, если train прошёл корректно.
            raise TrainingError(
                code="missing_zone_types",
                message=f"Нет ZoneType для предсказанной зоны id={predicted}",
            )

        log.debug(
            "[ml.wknn.classify] done",
            predicted_zone_id=predicted,
            confidence=confidence_value,
        )
        return ZoneClassification(
            zone_id=predicted,
            zone_type=zone_type,
            confidence=Confidence(confidence_value),
            classifier_name="wknn",
        )
