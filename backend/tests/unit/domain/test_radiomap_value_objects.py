"""Unit-тесты доменных value objects radiomap."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import BSSID, RSSIVector
from app.domain.shared.exceptions import ValidationError

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# BSSID
# ---------------------------------------------------------------------------


def test_bssid_normalizes_lowercase_to_upper() -> None:
    b = BSSID("aa:bb:cc:dd:ee:ff")
    assert b.value == "AA:BB:CC:DD:EE:FF"


def test_bssid_accepts_dash_separator() -> None:
    b = BSSID("aa-bb-cc-dd-ee-ff")
    assert b.value == "AA:BB:CC:DD:EE:FF"


def test_bssid_invalid_format_raises() -> None:
    for bad in ["G0:00:00:00:00:00", "AA:BB:CC:DD:EE", "not-a-mac", "AABBCCDDEEFF"]:
        with pytest.raises(ValidationError) as exc_info:
            BSSID(bad)
        assert exc_info.value.code == "invalid_bssid"


def test_bssid_non_string_raises() -> None:
    with pytest.raises(ValidationError):
        BSSID(12345)  # type: ignore[arg-type]


def test_bssid_equality_and_hash() -> None:
    a = BSSID("aa:bb:cc:dd:ee:01")
    b = BSSID("AA:BB:CC:DD:EE:01")
    c = BSSID("aa:bb:cc:dd:ee:02")
    assert a == b
    assert hash(a) == hash(b)
    assert a != c
    # hashable — можно класть в set/dict
    s = {a, b, c}
    assert len(s) == 2


# ---------------------------------------------------------------------------
# RSSIVector
# ---------------------------------------------------------------------------


def test_rssi_vector_round_trip() -> None:
    v = RSSIVector({"aa:bb:cc:dd:ee:01": -45, "AA:BB:CC:DD:EE:02": -67})
    assert len(v) == 2
    d = v.to_dict()
    assert d == {"AA:BB:CC:DD:EE:01": -45, "AA:BB:CC:DD:EE:02": -67}
    assert sorted(b.value for b in v.bssids()) == sorted(d.keys())


def test_rssi_vector_empty_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RSSIVector({})
    assert exc_info.value.code == "empty_rssi_vector"


def test_rssi_vector_too_many_aps_raises() -> None:
    samples = {f"AA:BB:CC:DD:EE:{i:02X}": -50 for i in range(201)}
    with pytest.raises(ValidationError) as exc_info:
        RSSIVector(samples)
    assert exc_info.value.code == "too_many_access_points"


def test_rssi_vector_value_above_zero_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RSSIVector({"AA:BB:CC:DD:EE:01": 5})
    assert exc_info.value.code == "rssi_out_of_range"


def test_rssi_vector_value_below_minus_100_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RSSIVector({"AA:BB:CC:DD:EE:01": -150})
    assert exc_info.value.code == "rssi_out_of_range"


def test_rssi_vector_non_int_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RSSIVector({"AA:BB:CC:DD:EE:01": -45.5})  # type: ignore[dict-item]
    assert exc_info.value.code == "invalid_rssi_value"


def test_rssi_vector_bool_rejected_as_value() -> None:
    """bool — подкласс int, но логически недопустим."""
    with pytest.raises(ValidationError):
        RSSIVector({"AA:BB:CC:DD:EE:01": True})  # type: ignore[dict-item]


def test_rssi_vector_invalid_bssid_key_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RSSIVector({"not-a-mac": -45})
    assert exc_info.value.code == "invalid_bssid"


def test_rssi_vector_equality_irrelevant_of_order() -> None:
    a = RSSIVector({"AA:BB:CC:DD:EE:01": -45, "AA:BB:CC:DD:EE:02": -67})
    b = RSSIVector({"AA:BB:CC:DD:EE:02": -67, "AA:BB:CC:DD:EE:01": -45})
    assert a == b
    assert hash(a) == hash(b)


# ---------------------------------------------------------------------------
# Fingerprint domain entity
# ---------------------------------------------------------------------------


def _make_vector() -> RSSIVector:
    return RSSIVector({"AA:BB:CC:DD:EE:01": -50})


def test_fingerprint_calibration_without_zone_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Fingerprint(
            id=0,
            employee_id=None,
            zone_id=None,
            is_calibration=True,
            captured_at=datetime.now(tz=UTC),
            device_id=None,
            rssi_vector=_make_vector(),
            sample_count=1,
        )
    assert exc_info.value.code == "calibration_requires_zone"


def test_fingerprint_naive_captured_at_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Fingerprint(
            id=0,
            employee_id=None,
            zone_id=None,
            is_calibration=False,
            captured_at=datetime(2026, 1, 1),  # без tz
            device_id=None,
            rssi_vector=_make_vector(),
            sample_count=1,
        )
    assert exc_info.value.code == "captured_at_must_be_timezone_aware"


def test_fingerprint_zero_sample_count_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Fingerprint(
            id=0,
            employee_id=42,
            zone_id=None,
            is_calibration=False,
            captured_at=datetime.now(tz=UTC),
            device_id=None,
            rssi_vector=_make_vector(),
            sample_count=0,
        )
    assert exc_info.value.code == "sample_count_must_be_positive"


def test_fingerprint_with_zone_helper() -> None:
    original = Fingerprint(
        id=1,
        employee_id=42,
        zone_id=None,
        is_calibration=False,
        captured_at=datetime.now(tz=UTC) - timedelta(seconds=1),
        device_id=None,
        rssi_vector=_make_vector(),
        sample_count=1,
    )
    updated = original.with_zone(7)
    assert updated.zone_id == 7
    assert original.zone_id is None  # frozen, не мутировался
