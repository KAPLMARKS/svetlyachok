"""Unit-тесты `RecordAttendanceUseCase` — 5-веточная логика open/extend/close."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import pytest

from app.application.attendance.record_attendance import (
    RecordAttendanceCommand,
    RecordAttendanceUseCase,
)
from app.domain.attendance.value_objects import AttendanceStatus
from app.domain.employees.entities import Employee, Role
from app.domain.shared.exceptions import NotFoundError, ValidationError
from app.domain.zones.entities import ZoneType
from tests.unit.application.fakes import (
    FakeAttendanceRepository,
    FakeEmployeeRepository,
)

pytestmark = pytest.mark.unit

INACTIVITY_TIMEOUT = timedelta(seconds=1800)  # 30 минут


@pytest.fixture
def attendance_repo() -> FakeAttendanceRepository:
    return FakeAttendanceRepository()


@pytest.fixture
def employee_repo() -> FakeEmployeeRepository:
    return FakeEmployeeRepository()


@pytest.fixture
async def employee_with_schedule(
    employee_repo: FakeEmployeeRepository,
) -> Employee:
    """Сотрудник с графиком 09:00–18:00."""
    return await employee_repo.add(
        Employee(
            id=0,
            email="emp@example.com",
            full_name="Иван Иванов",
            role=Role.EMPLOYEE,
            hashed_password="$2b$12$dummy.hash.for.testing.purposes.only.000000000",
            is_active=True,
            schedule_start=time(9, 0),
            schedule_end=time(18, 0),
        )
    )


@pytest.fixture
async def employee_no_schedule(
    employee_repo: FakeEmployeeRepository,
) -> Employee:
    """Сотрудник без графика."""
    return await employee_repo.add(
        Employee(
            id=0,
            email="noschedule@example.com",
            full_name="Без графика",
            role=Role.EMPLOYEE,
            hashed_password="$2b$12$dummy.hash.for.testing.purposes.only.000000000",
            is_active=True,
            schedule_start=None,
            schedule_end=None,
        )
    )


def _use_case(
    attendance_repo: FakeAttendanceRepository,
    employee_repo: FakeEmployeeRepository,
) -> RecordAttendanceUseCase:
    return RecordAttendanceUseCase(
        attendance_repo=attendance_repo,
        employee_repo=employee_repo,
        inactivity_timeout=INACTIVITY_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# Ветка 1: нет открытой сессии → создаём новую
# ---------------------------------------------------------------------------


async def test_opens_new_session_when_no_active(
    attendance_repo: FakeAttendanceRepository,
    employee_repo: FakeEmployeeRepository,
    employee_with_schedule: Employee,
) -> None:
    use_case = _use_case(attendance_repo, employee_repo)
    now = datetime(2026, 5, 2, 8, 0, tzinfo=UTC)  # до schedule_start (09:00)

    result = await use_case.execute(
        RecordAttendanceCommand(
            employee_id=employee_with_schedule.id,
            zone_id=10,
            zone_type=ZoneType.WORKPLACE,
            now=now,
        )
    )

    assert result.id == 1
    assert result.employee_id == employee_with_schedule.id
    assert result.zone_id == 10
    assert result.started_at == now
    assert result.last_seen_at == now
    assert result.ended_at is None
    assert result.status is AttendanceStatus.PRESENT


# ---------------------------------------------------------------------------
# Ветка 2: та же зона, в пределах timeout → продлеваем
# ---------------------------------------------------------------------------


async def test_extends_session_in_same_zone_within_timeout(
    attendance_repo: FakeAttendanceRepository,
    employee_repo: FakeEmployeeRepository,
    employee_with_schedule: Employee,
) -> None:
    use_case = _use_case(attendance_repo, employee_repo)
    open_at = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)
    extend_at = datetime(2026, 5, 2, 9, 20, tzinfo=UTC)  # 20 минут < 30

    first = await use_case.execute(
        RecordAttendanceCommand(
            employee_id=employee_with_schedule.id,
            zone_id=10,
            zone_type=ZoneType.WORKPLACE,
            now=open_at,
        )
    )
    assert first.is_open

    second = await use_case.execute(
        RecordAttendanceCommand(
            employee_id=employee_with_schedule.id,
            zone_id=10,
            zone_type=ZoneType.WORKPLACE,
            now=extend_at,
        )
    )

    assert second.id == first.id, "должна остаться та же сессия"
    assert second.started_at == open_at
    assert second.last_seen_at == extend_at
    assert second.ended_at is None
    # Только одна запись в репозитории.
    all_logs = await attendance_repo.list()
    assert len(all_logs) == 1


# ---------------------------------------------------------------------------
# Ветка 3: та же зона, ПОСЛЕ timeout → закрываем по last_seen_at, открываем новую
# ---------------------------------------------------------------------------


async def test_timeout_in_same_zone_closes_and_opens_new(
    attendance_repo: FakeAttendanceRepository,
    employee_repo: FakeEmployeeRepository,
    employee_with_schedule: Employee,
) -> None:
    use_case = _use_case(attendance_repo, employee_repo)
    open_at = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)
    after_timeout = datetime(2026, 5, 2, 11, 0, tzinfo=UTC)  # 2 часа > 30 мин

    first = await use_case.execute(
        RecordAttendanceCommand(
            employee_id=employee_with_schedule.id,
            zone_id=10,
            zone_type=ZoneType.WORKPLACE,
            now=open_at,
        )
    )
    new_session = await use_case.execute(
        RecordAttendanceCommand(
            employee_id=employee_with_schedule.id,
            zone_id=10,
            zone_type=ZoneType.WORKPLACE,
            now=after_timeout,
        )
    )

    # Первая сессия закрылась с ended_at = last_seen_at (= open_at, т.к. не
    # продлевалась). Use case клампит ended_at до started_at + 1µs, чтобы
    # удовлетворить CHECK-constraint `ended_at > started_at`.
    closed = await attendance_repo.get_by_id(first.id)
    assert closed is not None
    assert closed.ended_at is not None
    assert closed.ended_at > open_at
    assert (closed.ended_at - open_at).total_seconds() < 0.001
    assert closed.duration_seconds == 0  # int(1µs) == 0

    # Новая сессия открыта с started_at=after_timeout.
    assert new_session.id != first.id
    assert new_session.started_at == after_timeout
    assert new_session.is_open


# ---------------------------------------------------------------------------
# Ветка 4: другая зона → закрываем по now, открываем новую
# ---------------------------------------------------------------------------


async def test_zone_change_closes_and_opens_new(
    attendance_repo: FakeAttendanceRepository,
    employee_repo: FakeEmployeeRepository,
    employee_with_schedule: Employee,
) -> None:
    use_case = _use_case(attendance_repo, employee_repo)
    workplace_at = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)
    corridor_at = datetime(2026, 5, 2, 12, 30, tzinfo=UTC)

    first = await use_case.execute(
        RecordAttendanceCommand(
            employee_id=employee_with_schedule.id,
            zone_id=10,
            zone_type=ZoneType.WORKPLACE,
            now=workplace_at,
        )
    )
    second = await use_case.execute(
        RecordAttendanceCommand(
            employee_id=employee_with_schedule.id,
            zone_id=20,
            zone_type=ZoneType.CORRIDOR,
            now=corridor_at,
        )
    )

    closed = await attendance_repo.get_by_id(first.id)
    assert closed is not None
    assert closed.ended_at == corridor_at
    expected_duration = int((corridor_at - workplace_at).total_seconds())
    assert closed.duration_seconds == expected_duration

    assert second.id != first.id
    assert second.zone_id == 20
    assert second.started_at == corridor_at
    assert second.is_open


# ---------------------------------------------------------------------------
# Статус LATE при опоздании
# ---------------------------------------------------------------------------


async def test_status_late_when_started_after_schedule_start(
    attendance_repo: FakeAttendanceRepository,
    employee_repo: FakeEmployeeRepository,
    employee_with_schedule: Employee,
) -> None:
    use_case = _use_case(attendance_repo, employee_repo)
    late_at = datetime(2026, 5, 2, 10, 30, tzinfo=UTC)  # позже 09:00

    result = await use_case.execute(
        RecordAttendanceCommand(
            employee_id=employee_with_schedule.id,
            zone_id=10,
            zone_type=ZoneType.WORKPLACE,
            now=late_at,
        )
    )

    assert result.status is AttendanceStatus.LATE


# ---------------------------------------------------------------------------
# Без графика — статус всегда PRESENT
# ---------------------------------------------------------------------------


async def test_no_schedule_yields_present_regardless_of_time(
    attendance_repo: FakeAttendanceRepository,
    employee_repo: FakeEmployeeRepository,
    employee_no_schedule: Employee,
) -> None:
    use_case = _use_case(attendance_repo, employee_repo)
    very_late = datetime(2026, 5, 2, 23, 0, tzinfo=UTC)

    result = await use_case.execute(
        RecordAttendanceCommand(
            employee_id=employee_no_schedule.id,
            zone_id=10,
            zone_type=ZoneType.WORKPLACE,
            now=very_late,
        )
    )

    assert result.status is AttendanceStatus.PRESENT


# ---------------------------------------------------------------------------
# OVERTIME при закрытии после schedule_end
# ---------------------------------------------------------------------------


async def test_overtime_status_on_close_after_schedule_end(
    attendance_repo: FakeAttendanceRepository,
    employee_repo: FakeEmployeeRepository,
    employee_with_schedule: Employee,
) -> None:
    use_case = _use_case(attendance_repo, employee_repo)
    open_at = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)
    leave_at = datetime(2026, 5, 2, 19, 0, tzinfo=UTC)  # позже 18:00 → overtime

    first = await use_case.execute(
        RecordAttendanceCommand(
            employee_id=employee_with_schedule.id,
            zone_id=10,
            zone_type=ZoneType.WORKPLACE,
            now=open_at,
        )
    )
    # Смена зоны → закрытие первой.
    await use_case.execute(
        RecordAttendanceCommand(
            employee_id=employee_with_schedule.id,
            zone_id=99,
            zone_type=ZoneType.OUTSIDE_OFFICE,
            now=leave_at,
        )
    )

    closed = await attendance_repo.get_by_id(first.id)
    assert closed is not None
    assert closed.status is AttendanceStatus.OVERTIME


# ---------------------------------------------------------------------------
# Ошибки
# ---------------------------------------------------------------------------


async def test_employee_not_found_raises(
    attendance_repo: FakeAttendanceRepository,
    employee_repo: FakeEmployeeRepository,
) -> None:
    use_case = _use_case(attendance_repo, employee_repo)
    with pytest.raises(NotFoundError) as exc:
        await use_case.execute(
            RecordAttendanceCommand(
                employee_id=999,
                zone_id=1,
                zone_type=ZoneType.WORKPLACE,
                now=datetime.now(tz=UTC),
            )
        )
    assert exc.value.code == "employee_not_found"


async def test_naive_datetime_raises(
    attendance_repo: FakeAttendanceRepository,
    employee_repo: FakeEmployeeRepository,
    employee_with_schedule: Employee,
) -> None:
    use_case = _use_case(attendance_repo, employee_repo)
    with pytest.raises(ValidationError) as exc:
        await use_case.execute(
            RecordAttendanceCommand(
                employee_id=employee_with_schedule.id,
                zone_id=1,
                zone_type=ZoneType.WORKPLACE,
                now=datetime(2026, 5, 2, 9, 0),  # naive
            )
        )
    assert exc.value.code == "attendance_now_must_be_timezone_aware"
