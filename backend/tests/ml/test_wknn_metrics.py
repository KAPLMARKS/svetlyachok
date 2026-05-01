"""Метрологические тесты WKNN — Detection Probability на синтетике.

Эталонный baseline для главы «Метрологические результаты» диссертации.
На реальных полевых данных DP может отличаться (вероятно — лучше).
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
from app.infrastructure.ml.wknn_classifier import WknnClassifier

pytestmark = pytest.mark.ml


# Фиксированный seed numpy для воспроизводимости тестового набора.
_SEED = 42
_DP_THRESHOLD = 0.7  # минимальный порог Detection Probability на синтетике


def _generate_synthetic_dataset() -> tuple[
    list[Fingerprint],
    list[tuple[RSSIVector, int]],
    dict[int, ZoneType],
]:
    """4 зоны × 10 калибровочных + 4 зоны × 5 тестовых.

    Калибровочные точки разбросаны вокруг центра зоны с шумом
    ±2 dBm; тестовые — с шумом ±5 dBm (более жёстко). Центры зон
    различаются на 15+ dBm, чтобы они были физически разделимы.
    """
    rng = np.random.default_rng(_SEED)
    centers = {
        1: (-40, -55),  # workplace
        2: (-55, -70),  # corridor
        3: (-70, -45),  # meeting_room (другой паттерн!)
        4: (-85, -90),  # outside_office
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


def test_wknn_meets_dp_threshold() -> None:
    """WKNN на синтетике должен давать Detection Probability >= 0.7.

    На реальных полевых данных порог будет выше (типично 0.85+).
    Этот тест — нижняя граница для регрессий.
    """
    calibration, test_set, zone_types = _generate_synthetic_dataset()

    clf = WknnClassifier()
    clf.train(calibration, zone_types)

    metrics = evaluate_classifier(clf, test_set)

    # Логируем confusion matrix для визуального контроля
    zone_names = {zid: ztype.value for zid, ztype in zone_types.items()}
    print("\nWKNN confusion matrix:")
    print(format_confusion_matrix(metrics, zone_names))

    assert metrics.detection_probability >= _DP_THRESHOLD, (
        f"WKNN DP={metrics.detection_probability:.4f} < {_DP_THRESHOLD}. "
        f"Confusion: {metrics.confusion_matrix}"
    )

    # Все 4 зоны должны быть представлены в test set
    assert len(metrics.per_zone_detection_probability) == 4


def test_wknn_per_zone_dp_reasonable() -> None:
    """Per-zone DP не должна быть катастрофически плохой ни для одной зоны."""
    calibration, test_set, zone_types = _generate_synthetic_dataset()

    clf = WknnClassifier()
    clf.train(calibration, zone_types)

    metrics = evaluate_classifier(clf, test_set)

    for zid, dp in metrics.per_zone_detection_probability.items():
        # Минимум 0.4 на любую зону — иначе зона нечитаемо классифицируется.
        # На синтетике с 5 тестовыми точками 0.4 = 2/5 правильных.
        assert dp >= 0.4, (
            f"Per-zone DP для зоны {zid} = {dp:.4f} < 0.4. "
            "Возможно, зоны плохо разделимы или калибровка слишком шумная."
        )
