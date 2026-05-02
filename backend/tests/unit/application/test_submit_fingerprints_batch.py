"""Unit-тесты SubmitFingerprintsBatchUseCase.

Проверяют partial-success-семантику: один невалидный item не валит
весь batch; rejected содержит исходный index в массиве; код ошибки
проксируется из доменного `AppError.code`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.application.radiomap.submit_fingerprint import (
    SubmitFingerprintCommand,
    SubmitFingerprintUseCase,
)
from app.application.radiomap.submit_fingerprints_batch import (
    SubmitFingerprintsBatchCommand,
    SubmitFingerprintsBatchUseCase,
)
from app.domain.radiomap.value_objects import RSSIVector
from app.presentation.schemas.radiomap import FingerprintBulkSubmitRequest
from tests.unit.application.fakes import FakeFingerprintRepository

pytestmark = pytest.mark.unit


def _vector() -> RSSIVector:
    return RSSIVector({"AA:BB:CC:DD:EE:01": -55, "AA:BB:CC:DD:EE:02": -70})


def _make_use_case() -> SubmitFingerprintsBatchUseCase:
    submit = SubmitFingerprintUseCase(fingerprint_repo=FakeFingerprintRepository())
    return SubmitFingerprintsBatchUseCase(submit_use_case=submit)


def _cmd(captured_at: datetime, employee_id: int = 7) -> SubmitFingerprintCommand:
    return SubmitFingerprintCommand(
        employee_id=employee_id,
        captured_at=captured_at,
        device_id="dev-1",
        rssi_vector=_vector(),
        sample_count=1,
    )


async def test_all_items_accepted() -> None:
    use_case = _make_use_case()
    now = datetime.now(tz=UTC)

    result = await use_case.execute(
        SubmitFingerprintsBatchCommand(
            employee_id=7,
            items=[_cmd(now), _cmd(now - timedelta(seconds=10))],
        )
    )

    assert len(result.accepted) == 2
    assert result.rejected == []
    assert [a.index for a in result.accepted] == [0, 1]
    for a in result.accepted:
        assert a.fingerprint.employee_id == 7
        assert a.fingerprint.is_calibration is False


async def test_one_item_rejected_others_accepted() -> None:
    """`captured_at_in_future` у одного item не валит весь batch."""
    use_case = _make_use_case()
    now = datetime.now(tz=UTC)

    result = await use_case.execute(
        SubmitFingerprintsBatchCommand(
            employee_id=7,
            items=[
                _cmd(now),
                _cmd(now + timedelta(hours=1)),  # rejected
                _cmd(now - timedelta(seconds=30)),
            ],
        )
    )

    assert [a.index for a in result.accepted] == [0, 2]
    assert len(result.rejected) == 1
    rej = result.rejected[0]
    assert rej.index == 1
    assert rej.code == "captured_at_in_future"
    assert "будущ" in rej.message.lower() or rej.message  # сообщение присутствует


async def test_all_items_rejected() -> None:
    use_case = _make_use_case()
    now = datetime.now(tz=UTC)

    result = await use_case.execute(
        SubmitFingerprintsBatchCommand(
            employee_id=7,
            items=[
                _cmd(now + timedelta(hours=1)),
                _cmd(now - timedelta(days=10)),
            ],
        )
    )

    assert result.accepted == []
    assert [r.code for r in result.rejected] == [
        "captured_at_in_future",
        "captured_at_too_old",
    ]
    assert [r.index for r in result.rejected] == [0, 1]


async def test_rejected_index_matches_source_array() -> None:
    """Index в rejected — позиция в исходном массиве, не порядковый."""
    use_case = _make_use_case()
    now = datetime.now(tz=UTC)
    items = [
        _cmd(now),
        _cmd(now),
        _cmd(now + timedelta(hours=1)),  # index=2 → rejected
        _cmd(now),
    ]

    result = await use_case.execute(
        SubmitFingerprintsBatchCommand(employee_id=7, items=items)
    )

    assert [a.index for a in result.accepted] == [0, 1, 3]
    assert [r.index for r in result.rejected] == [2]


def test_empty_items_rejected_by_pydantic_schema() -> None:
    """Пустой массив items валится на Pydantic-валидации, а не в use case."""
    with pytest.raises(PydanticValidationError):
        FingerprintBulkSubmitRequest(items=[])


def test_too_many_items_rejected_by_pydantic_schema() -> None:
    """Свыше 100 items — Pydantic должен отбить запрос."""
    item = {
        "captured_at": datetime.now(tz=UTC),
        "rssi_vector": {"AA:BB:CC:DD:EE:01": -50},
        "sample_count": 1,
    }
    with pytest.raises(PydanticValidationError):
        FingerprintBulkSubmitRequest(items=[item] * 101)
