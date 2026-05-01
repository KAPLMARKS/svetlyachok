"""
Шаблон WKNN-классификатора для indoor-позиционирования.

Реализует доменный Protocol PositionClassifier через scikit-learn KNeighborsClassifier
с distance-weighting (weights="distance").

Принципы:
- Все гиперпараметры — через WknnConfig (нельзя хардкодить в классе)
- random_state фиксируется для воспроизводимости
- Тренировка отделена от инференса (fit раз, predict много)
- Логирование на DEBUG для отладки и WARN на низкой уверенности
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import structlog
from sklearn.neighbors import KNeighborsClassifier

# Доменные импорты — адаптировать под ваш проект.
# from app.domain.positioning.classifiers import PositionClassifier
# from app.domain.positioning.entities import ZoneClassification
# from app.domain.radiomap.entities import Fingerprint
# from app.domain.radiomap.value_objects import RSSIVector

from app.infrastructure.ml.features import (
    FeatureMatrix,
    MISSING_RSSI,
    build_feature_matrix,
)

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class WknnConfig:
    """Гиперпараметры WKNN. Версионируются в git как часть infrastructure/ml/config.py."""

    k: int = 5
    """Число ближайших соседей. Для indoor-позиционирования обычно 3..7."""

    metric: Literal["euclidean", "manhattan", "chebyshev"] = "euclidean"
    """Метрика расстояния. Сравнить в экспериментах для оптимального выбора."""

    weights: Literal["distance"] = "distance"
    """ВСЕГДА 'distance' — это и есть WKNN. 'uniform' = обычный KNN."""

    low_confidence_threshold: float = 0.4
    """Если максимальная вероятность класса < этого порога — логировать WARN."""

    def __post_init__(self) -> None:
        if not 1 <= self.k <= 50:
            raise ValueError(f"k must be in [1, 50], got {self.k}")
        if self.weights != "distance":
            raise ValueError("WKNN requires weights='distance' (use KNN class for 'uniform')")


class WknnClassifier:
    """
    Реализация PositionClassifier через scikit-learn KNN с distance-weighting.

    Использование:
        config = WknnConfig(k=5, metric="euclidean")
        classifier = WknnClassifier(config)
        classifier.fit(calibration_fingerprints)
        result = classifier.classify(observation)  # ZoneClassification
    """

    def __init__(self, config: WknnConfig) -> None:
        self._config = config
        self._sklearn_model: KNeighborsClassifier | None = None
        self._bssid_index: tuple[str, ...] | None = None
        self._classes: tuple[str, ...] | None = None
        log.debug(
            "[WknnClassifier.__init__] created",
            k=config.k,
            metric=config.metric,
            weights=config.weights,
        )

    def fit(self, calibration: list) -> None:  # list[Fingerprint]
        """
        Обучение классификатора на калибровочном сете.

        Должно вызываться один раз при старте сервиса (или при обновлении радиокарты),
        НЕ на каждый запрос классификации.
        """
        if not calibration:
            raise ValueError("[WknnClassifier.fit] calibration set is empty")

        feat = build_feature_matrix(calibration, bssid_index=None, include_labels=True)
        assert feat.y is not None  # noqa: S101 — гарантировано include_labels=True

        self._sklearn_model = KNeighborsClassifier(
            n_neighbors=min(self._config.k, len(feat.y)),
            weights=self._config.weights,
            metric=self._config.metric,
            n_jobs=-1,  # параллельная инференция
        )
        self._sklearn_model.fit(feat.X, feat.y)
        self._bssid_index = feat.bssid_index
        self._classes = tuple(self._sklearn_model.classes_.tolist())

        log.debug(
            "[WknnClassifier.fit] done",
            n_samples=feat.X.shape[0],
            n_features=feat.X.shape[1],
            n_classes=len(self._classes),
            classes=self._classes,
        )

    def classify(self, observation) -> dict:  # observation: RSSIVector → ZoneClassification
        """
        Классификация одного наблюдения.

        Возвращает доменный ZoneClassification (адаптировать под ваши модели).
        Здесь возвращён dict для шаблона.
        """
        if self._sklearn_model is None or self._bssid_index is None:
            raise RuntimeError(
                "[WknnClassifier.classify] model not trained. Call fit() first."
            )

        # Преобразовать одно наблюдение в плотный вектор
        observation_dict = observation.to_dict()  # {bssid: rssi}
        x = np.array(
            [observation_dict.get(bssid, MISSING_RSSI) for bssid in self._bssid_index],
            dtype=np.int16,
        ).reshape(1, -1)

        zone = str(self._sklearn_model.predict(x)[0])
        proba_vector = self._sklearn_model.predict_proba(x)[0]
        confidence = float(np.max(proba_vector))

        if confidence < self._config.low_confidence_threshold:
            log.warning(
                "[WknnClassifier.classify] low confidence prediction",
                zone=zone,
                confidence=confidence,
                threshold=self._config.low_confidence_threshold,
            )
        else:
            log.debug(
                "[WknnClassifier.classify] done",
                zone=zone,
                confidence=round(confidence, 3),
            )

        return {
            "zone": zone,
            "confidence": confidence,
            # Все вероятности по классам — полезно для downstream-анализа
            "probabilities": dict(zip(self._classes, proba_vector.tolist(), strict=True)),
        }

    def predict_batch(self, observations: list) -> list[dict]:  # list[RSSIVector] → list[ZoneClassification]
        """
        Batch-предсказание. Полезно для метрологической оценки на test-сете.

        Эффективнее, чем многократный вызов classify() — sklearn оптимизирует matrix ops.
        """
        if self._sklearn_model is None or self._bssid_index is None:
            raise RuntimeError("[WknnClassifier.predict_batch] model not trained")

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

        results = [
            {
                "zone": str(zones[i]),
                "confidence": float(np.max(proba[i])),
                "probabilities": dict(
                    zip(self._classes, proba[i].tolist(), strict=True)
                ),
            }
            for i in range(n)
        ]

        log.debug(
            "[WknnClassifier.predict_batch] done",
            batch_size=n,
            mean_confidence=round(float(np.mean(proba.max(axis=1))), 3),
        )
        return results
