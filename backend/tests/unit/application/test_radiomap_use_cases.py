"""Unit-тесты use cases радиоотпечатков и калибровки."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.radiomap.calibrate_radiomap import (
    CreateCalibrationPointCommand,
    CreateCalibrationPointUseCase,
)
from app.application.radiomap.delete_calibration_point import (
    DeleteCalibrationPointCommand,
    DeleteCalibrationPointUseCase,
)
from app.application.radiomap.list_calibration_points import (
    ListCalibrationPointsQuery,
    ListCalibrationPointsUseCase,
)
from app.application.radiomap.list_fingerprints import (
    GetFingerprintQuery,
    GetFingerprintUseCase,
    ListFingerprintsQuery,
    ListFingerprintsUseCase,
)
from app.application.radiomap.submit_fingerprint import (
    SubmitFingerprintCommand,
    SubmitFingerprintUseCase,
)
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.shared.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.domain.zones.entities import ZoneType
from tests.unit.application.fakes import FakeFingerprintRepository, FakeZoneRepository

pytestmark = pytest.mark.unit


def _vector() -> RSSIVector:
    return RSSIVector({"AA:BB:CC:DD:EE:01": -50, "AA:BB:CC:DD:EE:02": -67})


# ---------------------------------------------------------------------------
# SubmitFingerprintUseCase
# ---------------------------------------------------------------------------


async def test_submit_success() -> None:
    repo = FakeFingerprintRepository()
    use_case = SubmitFingerprintUseCase(fingerprint_repo=repo)

    fp = await use_case.execute(
        SubmitFingerprintCommand(
            employee_id=42,
            captured_at=datetime.now(tz=UTC),
            device_id="dev-1",
            rssi_vector=_vector(),
            sample_count=3,
        )
    )
    assert fp.id > 0
    assert fp.employee_id == 42
    assert fp.is_calibration is False
    assert fp.zone_id is None
    assert fp.sample_count == 3


async def test_submit_captured_at_in_future_rejected() -> None:
    repo = FakeFingerprintRepository()
    use_case = SubmitFingerprintUseCase(fingerprint_repo=repo)

    with pytest.raises(ValidationError) as exc_info:
        await use_case.execute(
            SubmitFingerprintCommand(
                employee_id=42,
                captured_at=datetime.now(tz=UTC) + timedelta(hours=1),
                device_id=None,
                rssi_vector=_vector(),
                sample_count=1,
            )
        )
    assert exc_info.value.code == "captured_at_in_future"


async def test_submit_captured_at_too_old_rejected() -> None:
    repo = FakeFingerprintRepository()
    use_case = SubmitFingerprintUseCase(fingerprint_repo=repo)

    with pytest.raises(ValidationError) as exc_info:
        await use_case.execute(
            SubmitFingerprintCommand(
                employee_id=42,
                captured_at=datetime.now(tz=UTC) - timedelta(days=10),
                device_id=None,
                rssi_vector=_vector(),
                sample_count=1,
            )
        )
    assert exc_info.value.code == "captured_at_too_old"


async def test_submit_clock_skew_within_tolerance_accepted() -> None:
    """Clock skew до 5 минут — норма (mobile часы редко идеально точны)."""
    repo = FakeFingerprintRepository()
    use_case = SubmitFingerprintUseCase(fingerprint_repo=repo)

    fp = await use_case.execute(
        SubmitFingerprintCommand(
            employee_id=42,
            captured_at=datetime.now(tz=UTC) + timedelta(minutes=2),
            device_id=None,
            rssi_vector=_vector(),
            sample_count=1,
        )
    )
    assert fp.id > 0


# ---------------------------------------------------------------------------
# CreateCalibrationPointUseCase
# ---------------------------------------------------------------------------


async def test_create_calibration_point_success() -> None:
    fp_repo = FakeFingerprintRepository()
    zone_repo = FakeZoneRepository()
    from app.domain.zones.entities import Zone

    zone = await zone_repo.add(Zone(id=0, name="Z1", type=ZoneType.WORKPLACE))

    use_case = CreateCalibrationPointUseCase(
        fingerprint_repo=fp_repo, zone_repo=zone_repo
    )
    fp = await use_case.execute(
        CreateCalibrationPointCommand(
            zone_id=zone.id,
            captured_at=datetime.now(tz=UTC),
            rssi_vector=_vector(),
            sample_count=5,
        )
    )
    assert fp.is_calibration is True
    assert fp.zone_id == zone.id


async def test_create_calibration_point_unknown_zone_raises() -> None:
    fp_repo = FakeFingerprintRepository()
    zone_repo = FakeZoneRepository()
    use_case = CreateCalibrationPointUseCase(
        fingerprint_repo=fp_repo, zone_repo=zone_repo
    )

    with pytest.raises(NotFoundError) as exc_info:
        await use_case.execute(
            CreateCalibrationPointCommand(
                zone_id=99999,
                captured_at=datetime.now(tz=UTC),
                rssi_vector=_vector(),
            )
        )
    assert exc_info.value.code == "zone_not_found"


# ---------------------------------------------------------------------------
# ListFingerprintsUseCase + GetFingerprintUseCase
# ---------------------------------------------------------------------------


async def _seed_three(repo: FakeFingerprintRepository) -> None:
    submit = SubmitFingerprintUseCase(fingerprint_repo=repo)
    base = datetime.now(tz=UTC)
    for i, employee_id in enumerate([1, 2, 1]):
        await submit.execute(
            SubmitFingerprintCommand(
                employee_id=employee_id,
                captured_at=base - timedelta(seconds=i),
                device_id=None,
                rssi_vector=_vector(),
                sample_count=1,
            )
        )


async def test_list_returns_all_when_no_filter() -> None:
    repo = FakeFingerprintRepository()
    await _seed_three(repo)

    use_case = ListFingerprintsUseCase(fingerprint_repo=repo)
    page = await use_case.execute(ListFingerprintsQuery())

    assert page.total == 3
    assert len(page.items) == 3


async def test_list_filter_by_employee() -> None:
    repo = FakeFingerprintRepository()
    await _seed_three(repo)

    use_case = ListFingerprintsUseCase(fingerprint_repo=repo)
    page = await use_case.execute(ListFingerprintsQuery(employee_id=1))
    assert page.total == 2
    assert all(fp.employee_id == 1 for fp in page.items)


async def test_get_fingerprint_unknown_raises() -> None:
    repo = FakeFingerprintRepository()
    use_case = GetFingerprintUseCase(fingerprint_repo=repo)

    with pytest.raises(NotFoundError) as exc_info:
        await use_case.execute(GetFingerprintQuery(fingerprint_id=99999))
    assert exc_info.value.code == "fingerprint_not_found"


# ---------------------------------------------------------------------------
# ListCalibrationPointsUseCase
# ---------------------------------------------------------------------------


async def test_list_calibration_returns_only_calibration() -> None:
    fp_repo = FakeFingerprintRepository()
    zone_repo = FakeZoneRepository()
    from app.domain.zones.entities import Zone

    zone = await zone_repo.add(Zone(id=0, name="Z1", type=ZoneType.WORKPLACE))

    create = CreateCalibrationPointUseCase(
        fingerprint_repo=fp_repo, zone_repo=zone_repo
    )
    submit = SubmitFingerprintUseCase(fingerprint_repo=fp_repo)

    await create.execute(
        CreateCalibrationPointCommand(
            zone_id=zone.id,
            captured_at=datetime.now(tz=UTC),
            rssi_vector=_vector(),
        )
    )
    await submit.execute(
        SubmitFingerprintCommand(
            employee_id=1,
            captured_at=datetime.now(tz=UTC),
            device_id=None,
            rssi_vector=_vector(),
            sample_count=1,
        )
    )

    use_case = ListCalibrationPointsUseCase(fingerprint_repo=fp_repo)
    page = await use_case.execute(ListCalibrationPointsQuery())

    assert page.total == 1
    assert page.items[0].is_calibration is True


# ---------------------------------------------------------------------------
# DeleteCalibrationPointUseCase
# ---------------------------------------------------------------------------


async def test_delete_calibration_point_success() -> None:
    fp_repo = FakeFingerprintRepository()
    zone_repo = FakeZoneRepository()
    from app.domain.zones.entities import Zone

    zone = await zone_repo.add(Zone(id=0, name="Z", type=ZoneType.WORKPLACE))

    create = CreateCalibrationPointUseCase(
        fingerprint_repo=fp_repo, zone_repo=zone_repo
    )
    fp = await create.execute(
        CreateCalibrationPointCommand(
            zone_id=zone.id,
            captured_at=datetime.now(tz=UTC),
            rssi_vector=_vector(),
        )
    )

    delete = DeleteCalibrationPointUseCase(fingerprint_repo=fp_repo)
    await delete.execute(DeleteCalibrationPointCommand(fingerprint_id=fp.id))

    assert await fp_repo.get_by_id(fp.id) is None


async def test_delete_calibration_rejects_live_fingerprint() -> None:
    """Защита: эндпоинт калибровки не должен удалять live-отпечаток."""
    fp_repo = FakeFingerprintRepository()
    submit = SubmitFingerprintUseCase(fingerprint_repo=fp_repo)
    fp = await submit.execute(
        SubmitFingerprintCommand(
            employee_id=42,
            captured_at=datetime.now(tz=UTC),
            device_id=None,
            rssi_vector=_vector(),
            sample_count=1,
        )
    )

    delete = DeleteCalibrationPointUseCase(fingerprint_repo=fp_repo)
    with pytest.raises(ValidationError) as exc_info:
        await delete.execute(DeleteCalibrationPointCommand(fingerprint_id=fp.id))
    assert exc_info.value.code == "not_a_calibration_point"


async def test_delete_calibration_unknown_id_raises() -> None:
    fp_repo = FakeFingerprintRepository()
    delete = DeleteCalibrationPointUseCase(fingerprint_repo=fp_repo)

    with pytest.raises(NotFoundError) as exc_info:
        await delete.execute(DeleteCalibrationPointCommand(fingerprint_id=99999))
    assert exc_info.value.code == "fingerprint_not_found"
