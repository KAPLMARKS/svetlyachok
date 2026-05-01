"""Unit-тесты ListEmployeesUseCase."""

from __future__ import annotations

import pytest

from app.application.employees.list_employees import (
    ListEmployeesQuery,
    ListEmployeesUseCase,
)
from app.domain.employees.entities import Employee, Role
from tests.unit.application.fakes import FakeEmployeeRepository

pytestmark = pytest.mark.unit


@pytest.fixture
async def populated_repo() -> FakeEmployeeRepository:
    repo = FakeEmployeeRepository()
    await repo.add(
        Employee(
            id=0,
            email="a@x.com",
            full_name="A",
            role=Role.ADMIN,
            hashed_password="h",
            is_active=True,
        )
    )
    await repo.add(
        Employee(
            id=0,
            email="b@x.com",
            full_name="B",
            role=Role.EMPLOYEE,
            hashed_password="h",
            is_active=True,
        )
    )
    await repo.add(
        Employee(
            id=0,
            email="c@x.com",
            full_name="C",
            role=Role.EMPLOYEE,
            hashed_password="h",
            is_active=False,
        )
    )
    return repo


async def test_list_no_filters_returns_all(
    populated_repo: FakeEmployeeRepository,
) -> None:
    use_case = ListEmployeesUseCase(employee_repo=populated_repo)
    page = await use_case.execute(ListEmployeesQuery())

    assert page.total == 3
    assert len(page.items) == 3


async def test_list_filter_by_role(populated_repo: FakeEmployeeRepository) -> None:
    use_case = ListEmployeesUseCase(employee_repo=populated_repo)
    page = await use_case.execute(ListEmployeesQuery(role=Role.ADMIN))

    assert page.total == 1
    assert page.items[0].email == "a@x.com"


async def test_list_filter_by_is_active(
    populated_repo: FakeEmployeeRepository,
) -> None:
    use_case = ListEmployeesUseCase(employee_repo=populated_repo)
    page = await use_case.execute(ListEmployeesQuery(is_active=False))

    assert page.total == 1
    assert page.items[0].email == "c@x.com"


async def test_list_pagination(populated_repo: FakeEmployeeRepository) -> None:
    use_case = ListEmployeesUseCase(employee_repo=populated_repo)
    page = await use_case.execute(ListEmployeesQuery(limit=2, offset=1))

    assert page.total == 3
    assert len(page.items) == 2
    assert page.items[0].email == "b@x.com"
    assert page.items[1].email == "c@x.com"


async def test_list_clamps_oversized_limit(
    populated_repo: FakeEmployeeRepository,
) -> None:
    use_case = ListEmployeesUseCase(employee_repo=populated_repo)
    page = await use_case.execute(ListEmployeesQuery(limit=10000))

    assert page.limit == 200  # _MAX_LIMIT
    assert len(page.items) == 3
