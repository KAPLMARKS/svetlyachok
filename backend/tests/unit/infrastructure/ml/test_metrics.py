"""Unit-тесты `metrics.py` — Detection Probability и confusion matrix."""

from __future__ import annotations

import pytest

from app.domain.positioning.classifiers import PositionClassifier
from app.domain.positioning.entities import ZoneClassification
from app.domain.positioning.value_objects import Confidence
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.zones.entities import ZoneType
from app.infrastructure.ml.metrics import (
    ClassificationMetrics,
    evaluate_classifier,
    format_confusion_matrix,
)

pytestmark = pytest.mark.unit


class _OracleClassifier(PositionClassifier):
    """Стуб классификатора, возвращающий заранее заданные результаты.

    На i-й вызов classify возвращает (predicted_zone_id, zone_type)
    из переданного списка. Используется, чтобы детерминированно
    проверить логику метрик.
    """

    def __init__(self, scripted: list[tuple[int, ZoneType]]) -> None:
        self._scripted = scripted
        self._idx = 0

    def is_trained(self) -> bool:
        return True

    def train(
        self,
        calibration_set: list[Fingerprint],
        zone_types: dict[int, ZoneType],
    ) -> None:
        # Stub. Не используется в тестах метрик.
        pass

    def classify(self, observation: RSSIVector) -> ZoneClassification:
        zid, ztype = self._scripted[self._idx]
        self._idx += 1
        return ZoneClassification(
            zone_id=zid,
            zone_type=ztype,
            confidence=Confidence(1.0),
            classifier_name="oracle",
        )


def _vec() -> RSSIVector:
    return RSSIVector({"AA:BB:CC:DD:EE:01": -50})


def test_evaluate_perfect_classifier_dp_one() -> None:
    """Все правильные → DP = 1.0."""
    test_set = [(_vec(), 1), (_vec(), 2), (_vec(), 1)]
    classifier = _OracleClassifier(
        [
            (1, ZoneType.WORKPLACE),
            (2, ZoneType.CORRIDOR),
            (1, ZoneType.WORKPLACE),
        ]
    )

    metrics = evaluate_classifier(classifier, test_set)

    assert metrics.total_samples == 3
    assert metrics.correct == 3
    assert metrics.detection_probability == 1.0
    assert metrics.per_zone_detection_probability == {1: 1.0, 2: 1.0}


def test_evaluate_all_wrong_dp_zero() -> None:
    """Все неправильные → DP = 0.0."""
    test_set = [(_vec(), 1), (_vec(), 2)]
    classifier = _OracleClassifier(
        [
            (3, ZoneType.MEETING_ROOM),  # должно быть 1
            (3, ZoneType.MEETING_ROOM),  # должно быть 2
        ]
    )

    metrics = evaluate_classifier(classifier, test_set)

    assert metrics.detection_probability == 0.0
    assert metrics.per_zone_detection_probability == {1: 0.0, 2: 0.0}


def test_evaluate_per_zone_dp() -> None:
    """Per-zone DP считается отдельно для каждой зоны."""
    # Зона 1: 2 правильных из 3 → 0.667
    # Зона 2: 1 правильный из 2 → 0.5
    test_set = [
        (_vec(), 1),
        (_vec(), 1),
        (_vec(), 1),
        (_vec(), 2),
        (_vec(), 2),
    ]
    classifier = _OracleClassifier(
        [
            (1, ZoneType.WORKPLACE),  # правильно
            (1, ZoneType.WORKPLACE),  # правильно
            (3, ZoneType.MEETING_ROOM),  # неправильно (true=1)
            (2, ZoneType.CORRIDOR),  # правильно
            (3, ZoneType.MEETING_ROOM),  # неправильно (true=2)
        ]
    )

    metrics = evaluate_classifier(classifier, test_set)

    assert metrics.detection_probability == pytest.approx(3 / 5)
    assert metrics.per_zone_detection_probability[1] == pytest.approx(2 / 3)
    assert metrics.per_zone_detection_probability[2] == pytest.approx(0.5)


def test_evaluate_confusion_matrix() -> None:
    """Confusion matrix корректно отражает все predicted/true пары."""
    test_set = [(_vec(), 1), (_vec(), 1), (_vec(), 2)]
    classifier = _OracleClassifier(
        [
            (1, ZoneType.WORKPLACE),  # (1, 1)
            (2, ZoneType.CORRIDOR),  # (2, 1) — ошибка
            (2, ZoneType.CORRIDOR),  # (2, 2)
        ]
    )

    metrics = evaluate_classifier(classifier, test_set)

    assert metrics.confusion_matrix[(1, 1)] == 1
    assert metrics.confusion_matrix[(2, 1)] == 1
    assert metrics.confusion_matrix[(2, 2)] == 1


def test_evaluate_empty_test_set() -> None:
    classifier = _OracleClassifier([])
    metrics = evaluate_classifier(classifier, [])
    assert metrics.total_samples == 0
    assert metrics.detection_probability == 0.0


def test_format_confusion_matrix_with_names() -> None:
    metrics = ClassificationMetrics(
        total_samples=3,
        correct=2,
        detection_probability=2 / 3,
        per_zone_detection_probability={1: 1.0, 2: 0.0},
        confusion_matrix={(1, 1): 2, (1, 2): 1},
    )
    output = format_confusion_matrix(
        metrics, zone_names={1: "workplace", 2: "corridor"}
    )
    # Содержит имена зон и общую DP
    assert "workplace" in output
    assert "corridor" in output
    assert "Overall DP" in output


def test_format_confusion_matrix_empty() -> None:
    metrics = ClassificationMetrics(
        total_samples=0, correct=0, detection_probability=0.0
    )
    output = format_confusion_matrix(metrics)
    assert "empty" in output.lower()
