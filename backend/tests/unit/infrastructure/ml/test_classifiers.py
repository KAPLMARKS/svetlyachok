"""Unit-тесты WKNN и Random Forest classifiers на synthetic data."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.positioning.classifiers import TrainingError
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.zones.entities import ZoneType
from app.infrastructure.ml.random_forest_classifier import (
    RandomForestClassifierImpl,
)
from app.infrastructure.ml.wknn_classifier import WknnClassifier

pytestmark = pytest.mark.unit


def _synthetic_calibration() -> tuple[list[Fingerprint], dict[int, ZoneType]]:
    """4 зоны × 5 калибровочных точек, линейно разделимые по 2 BSSID.

    Каждая зона имеет различающийся центр RSSI. Калибровочные точки
    близки к своему центру с малыми вариациями — идеальный
    test-bed для классификаторов.
    """
    centers = {1: -40, 2: -55, 3: -70, 4: -85}
    zone_types = {
        1: ZoneType.WORKPLACE,
        2: ZoneType.CORRIDOR,
        3: ZoneType.MEETING_ROOM,
        4: ZoneType.OUTSIDE_OFFICE,
    }
    fps = []
    for zid, center in centers.items():
        for i in range(5):
            fps.append(
                Fingerprint(
                    id=0,
                    employee_id=None,
                    zone_id=zid,
                    is_calibration=True,
                    captured_at=datetime.now(tz=UTC),
                    device_id=None,
                    rssi_vector=RSSIVector(
                        {
                            "AA:BB:CC:DD:EE:01": center + i,
                            "AA:BB:CC:DD:EE:02": center - 5,
                        }
                    ),
                    sample_count=1,
                )
            )
    return fps, zone_types


# ---------------------------------------------------------------------------
# WknnClassifier
# ---------------------------------------------------------------------------


def test_wknn_train_and_classify_correctly() -> None:
    fps, zone_types = _synthetic_calibration()
    clf = WknnClassifier()
    clf.train(fps, zone_types)

    # Observation очень близкое к центру зоны 1 (-40 dBm) → должно
    # классифицироваться как зона 1.
    result = clf.classify(
        RSSIVector(
            {"AA:BB:CC:DD:EE:01": -42, "AA:BB:CC:DD:EE:02": -45}
        )
    )
    assert result.zone_id == 1
    assert result.zone_type == ZoneType.WORKPLACE
    assert result.classifier_name == "wknn"
    assert 0.0 <= float(result.confidence) <= 1.0


def test_wknn_classifies_each_zone_correctly() -> None:
    """Все 4 зоны классифицируются правильно при observation у их центра."""
    fps, zone_types = _synthetic_calibration()
    clf = WknnClassifier()
    clf.train(fps, zone_types)

    for zid, expected_center in [(1, -40), (2, -55), (3, -70), (4, -85)]:
        result = clf.classify(
            RSSIVector(
                {
                    "AA:BB:CC:DD:EE:01": expected_center,
                    "AA:BB:CC:DD:EE:02": expected_center - 5,
                }
            )
        )
        assert result.zone_id == zid, (
            f"WKNN неверно: zone {zid} → predicted {result.zone_id}"
        )


def test_wknn_classify_before_train_raises() -> None:
    clf = WknnClassifier()
    with pytest.raises(TrainingError) as exc_info:
        clf.classify(RSSIVector({"AA:BB:CC:DD:EE:01": -50}))
    assert exc_info.value.code == "not_trained"


def test_wknn_is_trained_flag() -> None:
    clf = WknnClassifier()
    assert clf.is_trained() is False

    fps, zone_types = _synthetic_calibration()
    clf.train(fps, zone_types)
    assert clf.is_trained() is True


def test_wknn_train_empty_set_raises() -> None:
    clf = WknnClassifier()
    with pytest.raises(TrainingError) as exc_info:
        clf.train([], {})
    assert exc_info.value.code == "empty_calibration_set"


def test_wknn_train_missing_zone_types_raises() -> None:
    """Если в zone_types не передан тип зоны из калибровки — TrainingError."""
    fps, _ = _synthetic_calibration()
    # Передаём пустой zone_types — все зоны окажутся "missing"
    clf = WknnClassifier()
    with pytest.raises(TrainingError) as exc_info:
        clf.train(fps, {})
    assert exc_info.value.code == "missing_zone_types"


# ---------------------------------------------------------------------------
# RandomForestClassifierImpl
# ---------------------------------------------------------------------------


def test_random_forest_train_and_classify_correctly() -> None:
    fps, zone_types = _synthetic_calibration()
    clf = RandomForestClassifierImpl()
    clf.train(fps, zone_types)

    result = clf.classify(
        RSSIVector(
            {"AA:BB:CC:DD:EE:01": -42, "AA:BB:CC:DD:EE:02": -45}
        )
    )
    assert result.zone_id == 1
    assert result.classifier_name == "random_forest"
    assert 0.0 <= float(result.confidence) <= 1.0


def test_random_forest_results_reproducible() -> None:
    """random_state=42 → повторные запуски дают идентичный результат."""
    fps, zone_types = _synthetic_calibration()
    obs = RSSIVector(
        {"AA:BB:CC:DD:EE:01": -45, "AA:BB:CC:DD:EE:02": -50}
    )

    clf1 = RandomForestClassifierImpl()
    clf1.train(fps, zone_types)
    r1 = clf1.classify(obs)

    clf2 = RandomForestClassifierImpl()
    clf2.train(fps, zone_types)
    r2 = clf2.classify(obs)

    assert r1.zone_id == r2.zone_id
    assert float(r1.confidence) == float(r2.confidence)


def test_random_forest_classify_before_train_raises() -> None:
    clf = RandomForestClassifierImpl()
    with pytest.raises(TrainingError) as exc_info:
        clf.classify(RSSIVector({"AA:BB:CC:DD:EE:01": -50}))
    assert exc_info.value.code == "not_trained"
