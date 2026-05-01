"""Unit-тесты Deactivate/Activate use cases."""

from __future__ import annotations

import pytest

from app.application.employees.deactivate_employee import (
    ActivateEmployeeCommand,
    ActivateEmployeeUseCase,
    DeactivateEmployeeCommand,
    DeactivateEmployeeUseCase,
)
from app.domain.employees.entities import Employee, Role
from app.domain.shared.exceptions import ForbiddenError, NotFoundError
from tests.unit.application.fakes import FakeEmployeeRepository

pytestmark = pytest.mark.unit


@pytest.fixture
async def repo_with_users() -> tuple[FakeEmployeeRepository, Employee, Employee]:
    repo = FakeEmployeeRepository()
    admin = await repo.add(
        Employee(
            id=0,
            email="admin@x.com",
            full_name="Admin",
            role=Role.ADMIN,
            hashed_password="h",
            is_active=True,
        )
    )
    employee = await repo.add(
        Employee(
            id=0,
            email="emp@x.com",
            full_name="Emp",
            role=Role.EMPLOYEE,
            hashed_password="h",
            is_active=True,
        )
    )
    return repo, admin, employee


async def test_admin_deactivates_other_employee(
    repo_with_users: tuple[FakeEmployeeRepository, Employee, Employee],
) -> None:
    repo, admin, employee = repo_with_users
    use_case = DeactivateEmployeeUseCase(employee_repo=repo)

    result = await use_case.execute(
        DeactivateEmployeeCommand(
            employee_id=employee.id, current_user_id=admin.id
        )
    )
    assert result.is_active is False


async def test_admin_cannot_deactivate_self(
    repo_with_users: tuple[FakeEmployeeRepository, Employee, Employee],
) -> None:
    repo, admin, _ = repo_with_users
    use_case = DeactivateEmployeeUseCase(employee_repo=repo)

    with pytest.raises(ForbiddenError) as exc_info:
        await use_case.execute(
            DeactivateEmployeeCommand(
                employee_id=admin.id, current_user_id=admin.id
            )
        )
    assert exc_info.value.code == "cannot_deactivate_self"


async def test_deactivate_unknown_id_raises_not_found(
    repo_with_users: tuple[FakeEmployeeRepository, Employee, Employee],
) -> None:
    repo, admin, _ = repo_with_users
    use_case = DeactivateEmployeeUseCase(employee_repo=repo)

    with pytest.raises(NotFoundError):
        await use_case.execute(
            DeactivateEmployeeCommand(employee_id=99999, current_user_id=admin.id)
        )


async def test_deactivate_already_inactive_is_idempotent(
    repo_with_users: tuple[FakeEmployeeRepository, Employee, Employee],
) -> None:
    repo, admin, employee = repo_with_users
    use_case = DeactivateEmployeeUseCase(employee_repo=repo)

    # Сначала деактивируем.
    await use_case.execute(
        DeactivateEmployeeCommand(
            employee_id=employee.id, current_user_id=admin.id
        )
    )
    # Повторный вызов не падает, возвращает того же неактивного.
    result = await use_case.execute(
        DeactivateEmployeeCommand(
            employee_id=employee.id, current_user_id=admin.id
        )
    )
    assert result.is_active is False


async def test_activate_brings_back_inactive(
    repo_with_users: tuple[FakeEmployeeRepository, Employee, Employee],
) -> None:
    repo, admin, employee = repo_with_users
    deactivate = DeactivateEmployeeUseCase(employee_repo=repo)
    activate = ActivateEmployeeUseCase(employee_repo=repo)

    await deactivate.execute(
        DeactivateEmployeeCommand(
            employee_id=employee.id, current_user_id=admin.id
        )
    )
    result = await activate.execute(
        ActivateEmployeeCommand(employee_id=employee.id)
    )
    assert result.is_active is True
