"""Unit-тесты `features.py` — извлечение признаков из RSSI-векторов."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.positioning.classifiers import TrainingError
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import BSSID, RSSIVector
from app.infrastructure.ml.config import MISSING_RSSI
from app.infrastructure.ml.features import (
    build_feature_matrix,
    build_observation_vector,
)

pytestmark = pytest.mark.unit


def _fp(zid: int, samples: dict[str, int]) -> Fingerprint:
    """Helper: калибровочный отпечаток в одной зоне с timezone-aware ts."""
    return Fingerprint(
        id=0,
        employee_id=None,
        zone_id=zid,
        is_calibration=True,
        captured_at=datetime.now(tz=UTC),
        device_id=None,
        rssi_vector=RSSIVector(samples),
        sample_count=1,
    )


def _three_per_zone(zid: int, base: int) -> list[Fingerprint]:
    """3 калибровочных точки в одной зоне с лёгкими вариациями RSSI."""
    return [
        _fp(zid, {"AA:BB:CC:DD:EE:01": base, "AA:BB:CC:DD:EE:02": base - 5}),
        _fp(zid, {"AA:BB:CC:DD:EE:01": base + 1, "AA:BB:CC:DD:EE:02": base - 4}),
        _fp(zid, {"AA:BB:CC:DD:EE:01": base - 1, "AA:BB:CC:DD:EE:02": base - 6}),
    ]


# ---------------------------------------------------------------------------
# build_feature_matrix
# ---------------------------------------------------------------------------


def test_build_feature_matrix_basic() -> None:
    fps = _three_per_zone(1, -50) + _three_per_zone(2, -80)
    X, y, idx = build_feature_matrix(fps)

    assert X.shape == (6, 2)
    assert y.tolist() == [1, 1, 1, 2, 2, 2]
    assert [b.value for b in idx] == ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]


def test_missing_bssid_filled_with_noise_floor() -> None:
    """Sparse fingerprints — отсутствующие BSSID получают MISSING_RSSI."""
    fps = [
        # 3 в зоне 1: первая видит только BSSID:01, остальные оба
        _fp(1, {"AA:BB:CC:DD:EE:01": -50}),
        _fp(1, {"AA:BB:CC:DD:EE:01": -52, "AA:BB:CC:DD:EE:02": -60}),
        _fp(1, {"AA:BB:CC:DD:EE:01": -48, "AA:BB:CC:DD:EE:02": -62}),
        # 3 в зоне 2: только BSSID:02
        _fp(2, {"AA:BB:CC:DD:EE:02": -80}),
        _fp(2, {"AA:BB:CC:DD:EE:02": -82}),
        _fp(2, {"AA:BB:CC:DD:EE:02": -78}),
    ]
    X, _y, _idx = build_feature_matrix(fps)

    assert X.shape == (6, 2)
    # Первая строка: BSSID:01=-50, BSSID:02 отсутствует → MISSING_RSSI
    assert X[0, 0] == -50
    assert X[0, 1] == MISSING_RSSI
    # Четвёртая строка (зона 2 без BSSID:01): первая колонка — MISSING_RSSI
    assert X[3, 0] == MISSING_RSSI
    assert X[3, 1] == -80


def test_empty_calibration_raises_training_error() -> None:
    with pytest.raises(TrainingError) as exc_info:
        build_feature_matrix([])
    assert exc_info.value.code == "empty_calibration_set"


def test_too_few_points_per_zone_raises() -> None:
    """В зоне 2 только 2 точки — меньше MIN_CALIBRATION_POINTS_PER_ZONE=3."""
    fps = [
        *_three_per_zone(1, -50),
        _fp(2, {"AA:BB:CC:DD:EE:01": -80}),
        _fp(2, {"AA:BB:CC:DD:EE:01": -82}),
    ]
    with pytest.raises(TrainingError) as exc_info:
        build_feature_matrix(fps)
    assert exc_info.value.code == "insufficient_calibration_points"


def test_bssid_index_stable_across_calls() -> None:
    """Повторный вызов с теми же данными даёт идентичный bssid_index."""
    fps = _three_per_zone(1, -50) + _three_per_zone(2, -80)
    _, _, idx1 = build_feature_matrix(fps)
    _, _, idx2 = build_feature_matrix(fps)
    assert idx1 == idx2


def test_bssid_index_sorted() -> None:
    """BSSID порядок — лексикографически по value."""
    fps = _three_per_zone(1, -50) + _three_per_zone(2, -80)
    # Добавим ещё один BSSID, который должен оказаться посередине sorted-списка
    extra = _fp(1, {"AA:BB:CC:DD:EE:00": -45, "AA:BB:CC:DD:EE:01": -50})
    fps_with_extra = [extra, *fps]
    _, _, idx = build_feature_matrix(fps_with_extra)
    assert [b.value for b in idx] == sorted(b.value for b in idx)


# ---------------------------------------------------------------------------
# build_observation_vector
# ---------------------------------------------------------------------------


def test_observation_vector_uses_bssid_index_order() -> None:
    idx = [BSSID("AA:BB:CC:DD:EE:01"), BSSID("AA:BB:CC:DD:EE:02")]
    obs = RSSIVector({"AA:BB:CC:DD:EE:02": -67, "AA:BB:CC:DD:EE:01": -45})
    vec = build_observation_vector(obs, idx)

    assert vec.shape == (1, 2)
    assert vec[0, 0] == -45
    assert vec[0, 1] == -67


def test_observation_with_unknown_bssid_ignored() -> None:
    """BSSID, отсутствующий в bssid_index, не нарушает feature size."""
    idx = [BSSID("AA:BB:CC:DD:EE:01"), BSSID("AA:BB:CC:DD:EE:02")]
    obs = RSSIVector(
        {
            "AA:BB:CC:DD:EE:01": -45,
            "AA:BB:CC:DD:EE:99": -70,  # неизвестный BSSID
        }
    )
    vec = build_observation_vector(obs, idx)

    assert vec.shape == (1, 2)
    assert vec[0, 0] == -45
    # BSSID:02 не передан — заполняется MISSING_RSSI
    assert vec[0, 1] == MISSING_RSSI


def test_observation_empty_bssid_index_raises() -> None:
    """Пустой bssid_index означает «classifier не обучен»."""
    with pytest.raises(TrainingError) as exc_info:
        build_observation_vector(
            RSSIVector({"AA:BB:CC:DD:EE:01": -45}), bssid_index=[]
        )
    assert exc_info.value.code == "not_trained"
