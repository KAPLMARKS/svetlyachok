"""Random Forest-классификатор для baseline-сравнения с WKNN.

В дипломе сравниваем RF и WKNN на одном test set'е по ISO/IEC 18305.
Реализация — обёртка над `sklearn.ensemble.RandomForestClassifier`.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier as SklearnRandomForest

from app.core.logging import get_logger
from app.domain.positioning.classifiers import PositionClassifier, TrainingError
from app.domain.positioning.entities import ZoneClassification
from app.domain.positioning.value_objects import Confidence
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import BSSID, RSSIVector
from app.domain.zones.entities import ZoneType
from app.infrastructure.ml.config import RandomForestConfig
from app.infrastructure.ml.features import (
    build_feature_matrix,
    build_observation_vector,
)

log = get_logger(__name__)


class RandomForestClassifierImpl(PositionClassifier):
    """Random Forest для классификации позиции по RSSI."""

    def __init__(self, config: RandomForestConfig | None = None) -> None:
        self._config = config or RandomForestConfig()
        self._clf: SklearnRandomForest | None = None
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
            "[ml.random_forest.train] start",
            calibration_size=len(calibration_set),
            n_estimators=self._config.n_estimators,
            random_state=self._config.random_state,
        )

        X, y, bssid_index = build_feature_matrix(calibration_set)

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

        clf = SklearnRandomForest(
            n_estimators=self._config.n_estimators,
            max_depth=self._config.max_depth,
            min_samples_split=self._config.min_samples_split,
            class_weight=self._config.class_weight,
            random_state=self._config.random_state,
        )
        clf.fit(X, y)

        self._clf = clf
        self._bssid_index = bssid_index
        self._zone_types = zone_types

        log.info(
            "[ml.random_forest.train] done",
            n_samples=len(X),
            n_features=int(X.shape[1]),
            n_zones=len(unique_zones),
        )

    def classify(self, observation: RSSIVector) -> ZoneClassification:
        if not self.is_trained():
            raise TrainingError(
                code="not_trained",
                message=(
                    "RandomForestClassifier не обучен. "
                    "Вызовите train() перед classify()."
                ),
            )

        assert self._clf is not None
        assert self._bssid_index is not None

        vec = build_observation_vector(observation, self._bssid_index)
        predicted = int(self._clf.predict(vec)[0])
        proba = self._clf.predict_proba(vec)[0]
        confidence_value = float(np.max(proba))

        zone_type = self._zone_types.get(predicted)
        if zone_type is None:
            raise TrainingError(
                code="missing_zone_types",
                message=f"Нет ZoneType для предсказанной зоны id={predicted}",
            )

        log.debug(
            "[ml.random_forest.classify] done",
            predicted_zone_id=predicted,
            confidence=confidence_value,
        )
        return ZoneClassification(
            zone_id=predicted,
            zone_type=zone_type,
            confidence=Confidence(confidence_value),
            classifier_name="random_forest",
        )
