"""Unit-тесты `ListAttendanceUseCase` — фильтры + self-only для employee."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.attendance.list_attendance import (
    ListAttendanceQuery,
    ListAttendanceUseCase,
)
from app.domain.attendance.entities import AttendanceLog
from app.domain.attendance.value_objects import AttendanceStatus
from app.domain.employees.entities import Employee, Role
from app.domain.shared.exceptions import ForbiddenError
from tests.unit.application.fakes import FakeAttendanceRepository

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


async def _seed(repo: FakeAttendanceRepository) -> None:
    """Заполняет 3 сессии для employee_id=2 и 2 сессии для employee_id=3."""
    base = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)
    for i in range(3):
        await repo.add(
            AttendanceLog(
                id=0,
                employee_id=2,
                zone_id=10,
                started_at=base.replace(hour=9 + i),
                ended_at=base.replace(hour=10 + i),
                last_seen_at=base.replace(hour=10 + i),
                duration_seconds=3600,
                status=AttendanceStatus.PRESENT,
            )
        )
    for i in range(2):
        await repo.add(
            AttendanceLog(
                id=0,
                employee_id=3,
                zone_id=20,
                started_at=base.replace(hour=9 + i),
                ended_at=base.replace(hour=10 + i),
                last_seen_at=base.replace(hour=10 + i),
                duration_seconds=3600,
                status=AttendanceStatus.LATE,
            )
        )


async def test_admin_sees_all_employees() -> None:
    repo = FakeAttendanceRepository()
    await _seed(repo)
    use_case = ListAttendanceUseCase(attendance_repo=repo)

    page = await use_case.execute(
        ListAttendanceQuery(requesting_user=_admin())
    )

    assert page.total == 5
    assert len(page.items) == 5


async def test_employee_sees_only_self_when_no_filter() -> None:
    repo = FakeAttendanceRepository()
    await _seed(repo)
    use_case = ListAttendanceUseCase(attendance_repo=repo)

    employee = _employee(emp_id=2)
    page = await use_case.execute(
        ListAttendanceQuery(requesting_user=employee)
    )

    assert page.total == 3
    assert all(item.employee_id == 2 for item in page.items)


async def test_employee_forbidden_to_request_other_employee() -> None:
    repo = FakeAttendanceRepository()
    await _seed(repo)
    use_case = ListAttendanceUseCase(attendance_repo=repo)

    employee = _employee(emp_id=2)
    with pytest.raises(ForbiddenError) as exc:
        await use_case.execute(
            ListAttendanceQuery(requesting_user=employee, employee_id=3)
        )
    assert exc.value.code == "attendance_self_only"


async def test_filter_by_zone_and_status() -> None:
    repo = FakeAttendanceRepository()
    await _seed(repo)
    use_case = ListAttendanceUseCase(attendance_repo=repo)

    page = await use_case.execute(
        ListAttendanceQuery(
            requesting_user=_admin(),
            zone_id=20,
            status=AttendanceStatus.LATE,
        )
    )

    assert page.total == 2
    assert all(item.zone_id == 20 for item in page.items)
    assert all(item.status is AttendanceStatus.LATE for item in page.items)
