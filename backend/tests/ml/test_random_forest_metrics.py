"""Метрологические тесты Random Forest — DP на синтетике.

Сравнительный baseline с WKNN на ОДИНАКОВОМ test set'е (один seed).
Это позволяет в дипломе показать численное сравнение двух
классификаторов на воспроизводимых данных.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.zones.entities import ZoneType
from app.infrastructure.ml.metrics import (
    evaluate_classifier,
    format_confusion_matrix,
)
from app.infrastructure.ml.random_forest_classifier import (
    RandomForestClassifierImpl,
)

pytestmark = pytest.mark.ml


# Тот же seed, что и в test_wknn_metrics — для корректного сравнения
# на ОДНОМ test set'е (требование ISO/IEC 18305).
_SEED = 42
_DP_THRESHOLD = 0.7


def _generate_synthetic_dataset() -> tuple[
    list[Fingerprint],
    list[tuple[RSSIVector, int]],
    dict[int, ZoneType],
]:
    """Идентично с test_wknn_metrics — критично для сравнения."""
    rng = np.random.default_rng(_SEED)
    centers = {
        1: (-40, -55),
        2: (-55, -70),
        3: (-70, -45),
        4: (-85, -90),
    }
    zone_types = {
        1: ZoneType.WORKPLACE,
        2: ZoneType.CORRIDOR,
        3: ZoneType.MEETING_ROOM,
        4: ZoneType.OUTSIDE_OFFICE,
    }

    calibration: list[Fingerprint] = []
    for zid, (c1, c2) in centers.items():
        for _ in range(10):
            noise = rng.uniform(-2, 2, size=2)
            calibration.append(
                Fingerprint(
                    id=0,
                    employee_id=None,
                    zone_id=zid,
                    is_calibration=True,
                    captured_at=datetime.now(tz=UTC),
                    device_id="cal",
                    rssi_vector=RSSIVector(
                        {
                            "AA:BB:CC:DD:EE:01": round(c1 + noise[0]),
                            "AA:BB:CC:DD:EE:02": round(c2 + noise[1]),
                        }
                    ),
                    sample_count=1,
                )
            )

    test_set: list[tuple[RSSIVector, int]] = []
    for zid, (c1, c2) in centers.items():
        for _ in range(5):
            noise = rng.uniform(-5, 5, size=2)
            obs = RSSIVector(
                {
                    "AA:BB:CC:DD:EE:01": round(c1 + noise[0]),
                    "AA:BB:CC:DD:EE:02": round(c2 + noise[1]),
                }
            )
            test_set.append((obs, zid))

    return calibration, test_set, zone_types


def test_random_forest_meets_dp_threshold() -> None:
    calibration, test_set, zone_types = _generate_synthetic_dataset()

    clf = RandomForestClassifierImpl()
    clf.train(calibration, zone_types)

    metrics = evaluate_classifier(clf, test_set)

    zone_names = {zid: ztype.value for zid, ztype in zone_types.items()}
    print("\nRandom Forest confusion matrix:")
    print(format_confusion_matrix(metrics, zone_names))

    assert metrics.detection_probability >= _DP_THRESHOLD, (
        f"RF DP={metrics.detection_probability:.4f} < {_DP_THRESHOLD}. "
        f"Confusion: {metrics.confusion_matrix}"
    )


def test_random_forest_reproducible_on_same_seed() -> None:
    """random_state=42 → повторный запуск даёт идентичные метрики.

    Критично для ISO/IEC 18305 экспериментов: повторение без
    изменения данных и параметров должно давать побитово
    одинаковый результат.
    """
    calibration, test_set, zone_types = _generate_synthetic_dataset()

    clf1 = RandomForestClassifierImpl()
    clf1.train(calibration, zone_types)
    metrics1 = evaluate_classifier(clf1, test_set)

    clf2 = RandomForestClassifierImpl()
    clf2.train(calibration, zone_types)
    metrics2 = evaluate_classifier(clf2, test_set)

    assert metrics1.detection_probability == metrics2.detection_probability
    assert metrics1.confusion_matrix == metrics2.confusion_matrix
