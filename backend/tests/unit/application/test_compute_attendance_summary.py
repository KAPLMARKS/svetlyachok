"""Unit-тесты `ComputeAttendanceSummaryUseCase` — агрегация по периоду."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.attendance.compute_summary import (
    AttendanceSummaryQuery,
    ComputeAttendanceSummaryUseCase,
)
from app.domain.attendance.entities import AttendanceLog
from app.domain.attendance.value_objects import AttendanceStatus, WorkInterval
from app.domain.employees.entities import Employee, Role
from app.domain.shared.exceptions import ForbiddenError
from app.domain.zones.entities import Zone, ZoneType
from tests.unit.application.fakes import (
    FakeAttendanceRepository,
    FakeZoneRepository,
)

pytestmark = pytest.mark.unit


def _admin() -> Employee:
    return Employee(
        id=1,
        email="admin@example.com",
        full_name="Admin",
        role=Role.ADMIN,
        hashed_password="$2b$12$dummy.hash.for.testing.purposes.only.000000000",
        is_active=True,
    )


def _employee(emp_id: int = 2) -> Employee:
    return Employee(
        id=emp_id,
        email=f"emp{emp_id}@example.com",
        full_name=f"Employee {emp_id}",
        role=Role.EMPLOYEE,
        hashed_password="$2b$12$dummy.hash.for.testing.purposes.only.000000000",
        is_active=True,
    )


async def _seed_zones(zone_repo: FakeZoneRepository) -> tuple[Zone, Zone]:
    """Создаёт workplace (id=1) и corridor (id=2)."""
    workplace = await zone_repo.add(
        Zone(id=0, name="Workplace 1", type=ZoneType.WORKPLACE)
    )
    corridor = await zone_repo.add(
        Zone(id=0, name="Corridor", type=ZoneType.CORRIDOR)
    )
    return workplace, corridor


@pytest.fixture
def period() -> WorkInterval:
    return WorkInterval(
        start=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        end=datetime(2026, 5, 31, 23, 59, tzinfo=UTC),
    )


async def test_work_hours_total_from_workplace_only(period: WorkInterval) -> None:
    attendance_repo = FakeAttendanceRepository()
    zone_repo = FakeZoneRepository()
    workplace, corridor = await _seed_zones(zone_repo)
    base = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)

    # 2 часа в workplace.
    await attendance_repo.add(
        AttendanceLog(
            id=0,
            employee_id=2,
            zone_id=workplace.id,
            started_at=base,
            ended_at=base.replace(hour=11),
            last_seen_at=base.replace(hour=11),
            duration_seconds=2 * 3600,
            status=AttendanceStatus.PRESENT,
        )
    )
    # 1 час в corridor — не должен попасть в work_hours_total.
    await attendance_repo.add(
        AttendanceLog(
            id=0,
            employee_id=2,
            zone_id=corridor.id,
            started_at=base.replace(hour=11),
            ended_at=base.replace(hour=12),
            last_seen_at=base.replace(hour=12),
            duration_seconds=3600,
            status=AttendanceStatus.PRESENT,
        )
    )

    use_case = ComputeAttendanceSummaryUseCase(
        attendance_repo=attendance_repo, zone_repo=zone_repo
    )
    summary = await use_case.execute(
        AttendanceSummaryQuery(
            requesting_user=_admin(),
            employee_id=2,
            period=period,
        )
    )

    assert summary.work_hours_total == 2.0
    assert summary.sessions_count == 2


async def test_lateness_count(period: WorkInterval) -> None:
    attendance_repo = FakeAttendanceRepository()
    zone_repo = FakeZoneRepository()
    workplace, _ = await _seed_zones(zone_repo)
    base = datetime(2026, 5, 2, 9, 30, tzinfo=UTC)

    for i in range(3):
        await attendance_repo.add(
            AttendanceLog(
                id=0,
                employee_id=2,
                zone_id=workplace.id,
                started_at=base.replace(day=2 + i),
                ended_at=base.replace(day=2 + i, hour=18),
                last_seen_at=base.replace(day=2 + i, hour=18),
                duration_seconds=8 * 3600,
                status=AttendanceStatus.LATE,
            )
        )
    # Одна сессия PRESENT — не должна добавиться в lateness_count.
    await attendance_repo.add(
        AttendanceLog(
            id=0,
            employee_id=2,
            zone_id=workplace.id,
            started_at=base.replace(day=10, hour=9),
            ended_at=base.replace(day=10, hour=18),
            last_seen_at=base.replace(day=10, hour=18),
            duration_seconds=9 * 3600,
            status=AttendanceStatus.PRESENT,
        )
    )

    use_case = ComputeAttendanceSummaryUseCase(
        attendance_repo=attendance_repo, zone_repo=zone_repo
    )
    summary = await use_case.execute(
        AttendanceSummaryQuery(
            requesting_user=_admin(),
            employee_id=2,
            period=period,
        )
    )

    assert summary.lateness_count == 3


async def test_overtime_seconds_total(period: WorkInterval) -> None:
    attendance_repo = FakeAttendanceRepository()
    zone_repo = FakeZoneRepository()
    workplace, _ = await _seed_zones(zone_repo)
    base = datetime(2026, 5, 2, 18, 0, tzinfo=UTC)

    await attendance_repo.add(
        AttendanceLog(
            id=0,
            employee_id=2,
            zone_id=workplace.id,
            started_at=base,
            ended_at=base.replace(hour=20),  # +2 часа = 7200 сек
            last_seen_at=base.replace(hour=20),
            duration_seconds=2 * 3600,
            status=AttendanceStatus.OVERTIME,
        )
    )

    use_case = ComputeAttendanceSummaryUseCase(
        attendance_repo=attendance_repo, zone_repo=zone_repo
    )
    summary = await use_case.execute(
        AttendanceSummaryQuery(
            requesting_user=_admin(),
            employee_id=2,
            period=period,
        )
    )

    assert summary.overtime_seconds_total == 7200


async def test_open_session_excluded_from_aggregates(period: WorkInterval) -> None:
    attendance_repo = FakeAttendanceRepository()
    zone_repo = FakeZoneRepository()
    workplace, _ = await _seed_zones(zone_repo)
    base = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)

    # Закрытая сессия 1 час.
    await attendance_repo.add(
        AttendanceLog(
            id=0,
            employee_id=2,
            zone_id=workplace.id,
            started_at=base,
            ended_at=base.replace(hour=10),
            last_seen_at=base.replace(hour=10),
            duration_seconds=3600,
            status=AttendanceStatus.PRESENT,
        )
    )
    # Открытая сессия (продолжается).
    await attendance_repo.add(
        AttendanceLog(
            id=0,
            employee_id=2,
            zone_id=workplace.id,
            started_at=base.replace(hour=11),
            ended_at=None,
            last_seen_at=base.replace(hour=12),
            duration_seconds=None,
            status=AttendanceStatus.PRESENT,
        )
    )

    use_case = ComputeAttendanceSummaryUseCase(
        attendance_repo=attendance_repo, zone_repo=zone_repo
    )
    summary = await use_case.execute(
        AttendanceSummaryQuery(
            requesting_user=_admin(),
            employee_id=2,
            period=period,
        )
    )

    # work_hours_total — только закрытая сессия.
    assert summary.work_hours_total == 1.0
    # sessions_count — все, включая открытую.
    assert summary.sessions_count == 2


async def test_employee_self_only_forbidden(period: WorkInterval) -> None:
    attendance_repo = FakeAttendanceRepository()
    zone_repo = FakeZoneRepository()
    await _seed_zones(zone_repo)

    use_case = ComputeAttendanceSummaryUseCase(
        attendance_repo=attendance_repo, zone_repo=zone_repo
    )
    employee = _employee(emp_id=2)
    with pytest.raises(ForbiddenError) as exc:
        await use_case.execute(
            AttendanceSummaryQuery(
                requesting_user=employee,
                employee_id=99,  # чужой
                period=period,
            )
        )
    assert exc.value.code == "attendance_self_only"
