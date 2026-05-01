"""
Шаблон Random Forest классификатора для indoor-позиционирования.

Реализует тот же доменный Protocol PositionClassifier, что и WKNN.
Используется для сравнительного анализа в дипломной работе.

Принципы:
- random_state ОБЯЗАТЕЛЬНО зафиксирован (по умолчанию 42)
- class_weight="balanced" — типично калибровочные точки распределены неравномерно
- n_jobs=-1 для параллельной тренировки на всех ядрах
- feature_importances_ доступен для анализа важности BSSID в дипломе
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog
from sklearn.ensemble import RandomForestClassifier

from app.infrastructure.ml.features import (
    FeatureMatrix,
    MISSING_RSSI,
    build_feature_matrix,
)

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RandomForestConfig:
    """Гиперпараметры Random Forest. Версионируются в git."""

    n_estimators: int = 100
    """Число деревьев. 50..500. Больше — выше точность и время обучения."""

    max_depth: int | None = None
    """Максимальная глубина дерева. None = без ограничения."""

    min_samples_split: int = 2
    """Минимум samples для разделения узла."""

    min_samples_leaf: int = 1
    """Минимум samples в листе."""

    class_weight: str = "balanced"
    """Балансировка весов классов. 'balanced' — обязательно для несбалансированного сета."""

    random_state: int = 42
    """Фиксированное значение для воспроизводимости. НЕ менять между экспериментами одного типа."""

    low_confidence_threshold: float = 0.4
    """Если max(predict_proba) < этого порога — лог WARN."""

    def __post_init__(self) -> None:
        if not 1 <= self.n_estimators <= 1000:
            raise ValueError(f"n_estimators must be in [1, 1000], got {self.n_estimators}")


class RandomForestClassifierWrapper:
    """Реализация PositionClassifier через scikit-learn Random Forest."""

    def __init__(self, config: RandomForestConfig) -> None:
        self._config = config
        self._sklearn_model: RandomForestClassifier | None = None
        self._bssid_index: tuple[str, ...] | None = None
        self._classes: tuple[str, ...] | None = None
        log.debug(
            "[RandomForestClassifierWrapper.__init__] created",
            n_estimators=config.n_estimators,
            max_depth=config.max_depth,
            random_state=config.random_state,
        )

    def fit(self, calibration: list) -> None:  # list[Fingerprint]
        if not calibration:
            raise ValueError("[RandomForestClassifierWrapper.fit] calibration set is empty")

        feat = build_feature_matrix(calibration, bssid_index=None, include_labels=True)
        assert feat.y is not None  # noqa: S101

        self._sklearn_model = RandomForestClassifier(
            n_estimators=self._config.n_estimators,
            max_depth=self._config.max_depth,
            min_samples_split=self._config.min_samples_split,
            min_samples_leaf=self._config.min_samples_leaf,
            class_weight=self._config.class_weight,
            random_state=self._config.random_state,
            n_jobs=-1,
        )
        self._sklearn_model.fit(feat.X, feat.y)
        self._bssid_index = feat.bssid_index
        self._classes = tuple(self._sklearn_model.classes_.tolist())

        log.debug(
            "[RandomForestClassifierWrapper.fit] done",
            n_samples=feat.X.shape[0],
            n_features=feat.X.shape[1],
            n_classes=len(self._classes),
            n_trees_actual=len(self._sklearn_model.estimators_),
        )

    def classify(self, observation) -> dict:
        """Классификация одного наблюдения."""
        if self._sklearn_model is None or self._bssid_index is None:
            raise RuntimeError(
                "[RandomForestClassifierWrapper.classify] model not trained"
            )

        observation_dict = observation.to_dict()
        x = np.array(
            [observation_dict.get(bssid, MISSING_RSSI) for bssid in self._bssid_index],
            dtype=np.int16,
        ).reshape(1, -1)

        zone = str(self._sklearn_model.predict(x)[0])
        proba_vector = self._sklearn_model.predict_proba(x)[0]
        confidence = float(np.max(proba_vector))

        if confidence < self._config.low_confidence_threshold:
            log.warning(
                "[RandomForestClassifierWrapper.classify] low confidence prediction",
                zone=zone,
                confidence=confidence,
            )
        else:
            log.debug(
                "[RandomForestClassifierWrapper.classify] done",
                zone=zone,
                confidence=round(confidence, 3),
            )

        return {
            "zone": zone,
            "confidence": confidence,
            "probabilities": dict(zip(self._classes, proba_vector.tolist(), strict=True)),
        }

    def predict_batch(self, observations: list) -> list[dict]:
        """Batch-предсказание для метрологической оценки."""
        if self._sklearn_model is None or self._bssid_index is None:
            raise RuntimeError("[RandomForestClassifierWrapper.predict_batch] model not trained")

        n = len(observations)
        X = np.full(
            (n, len(self._bssid_index)),
            fill_value=MISSING_RSSI,
            dtype=np.int16,
        )
        bssid_to_col = {bssid: idx for idx, bssid in enumerate(self._bssid_index)}
        for row_idx, obs in enumerate(observations):
            for bssid, rssi in obs.to_dict().items():
                col = bssid_to_col.get(bssid)
                if col is not None:
                    X[row_idx, col] = rssi

        zones = self._sklearn_model.predict(X)
        proba = self._sklearn_model.predict_proba(X)

        return [
            {
                "zone": str(zones[i]),
                "confidence": float(np.max(proba[i])),
                "probabilities": dict(
                    zip(self._classes, proba[i].tolist(), strict=True)
                ),
            }
            for i in range(n)
        ]

    def feature_importances(self) -> dict[str, float]:
        """
        Возвращает словарь {bssid: importance} с важностью каждого AP для классификации.

        Используется в дипломе для анализа: какие точки доступа критичны для разделения зон.
        Можно отсортировать по убыванию и показать top-10 в работе.
        """
        if self._sklearn_model is None or self._bssid_index is None:
            raise RuntimeError("[feature_importances] model not trained")

        importances = self._sklearn_model.feature_importances_
        return dict(zip(self._bssid_index, importances.tolist(), strict=True))
