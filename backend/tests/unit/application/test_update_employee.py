"""Unit-тесты UpdateEmployeeUseCase."""

from __future__ import annotations

from datetime import time

import pytest

from app.application.employees.update_employee import (
    UpdateEmployeeCommand,
    UpdateEmployeeUseCase,
)
from app.domain.employees.entities import Employee, Role
from app.domain.shared.exceptions import NotFoundError
from tests.unit.application.fakes import FakeEmployeeRepository

pytestmark = pytest.mark.unit


@pytest.fixture
async def repo_with_user() -> tuple[FakeEmployeeRepository, Employee]:
    repo = FakeEmployeeRepository()
    user = await repo.add(
        Employee(
            id=0,
            email="user@x.com",
            full_name="Старое имя",
            role=Role.EMPLOYEE,
            hashed_password="h",
            is_active=True,
            schedule_start=time(9, 0),
            schedule_end=time(18, 0),
        )
    )
    return repo, user


async def test_update_partial_only_changes_provided_fields(
    repo_with_user: tuple[FakeEmployeeRepository, Employee],
) -> None:
    repo, user = repo_with_user
    use_case = UpdateEmployeeUseCase(employee_repo=repo)

    result = await use_case.execute(
        UpdateEmployeeCommand(
            employee_id=user.id,
            full_name="Новое имя",
        )
    )

    assert result.full_name == "Новое имя"
    assert result.role is Role.EMPLOYEE  # не менялась
    assert result.schedule_start == time(9, 0)  # не менялась
    assert result.email == "user@x.com"  # не передавалась


async def test_update_can_change_role(
    repo_with_user: tuple[FakeEmployeeRepository, Employee],
) -> None:
    repo, user = repo_with_user
    use_case = UpdateEmployeeUseCase(employee_repo=repo)

    result = await use_case.execute(
        UpdateEmployeeCommand(employee_id=user.id, role=Role.ADMIN)
    )
    assert result.role is Role.ADMIN


async def test_update_clear_schedule(
    repo_with_user: tuple[FakeEmployeeRepository, Employee],
) -> None:
    repo, user = repo_with_user
    use_case = UpdateEmployeeUseCase(employee_repo=repo)

    result = await use_case.execute(
        UpdateEmployeeCommand(
            employee_id=user.id,
            clear_schedule_start=True,
            clear_schedule_end=True,
        )
    )
    assert result.schedule_start is None
    assert result.schedule_end is None


async def test_update_unknown_id_raises_not_found(
    repo_with_user: tuple[FakeEmployeeRepository, Employee],
) -> None:
    repo, _ = repo_with_user
    use_case = UpdateEmployeeUseCase(employee_repo=repo)

    with pytest.raises(NotFoundError) as exc_info:
        await use_case.execute(UpdateEmployeeCommand(employee_id=99999))
    assert exc_info.value.code == "employee_not_found"
