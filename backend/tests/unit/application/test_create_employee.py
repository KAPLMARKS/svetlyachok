"""Unit-тесты CreateEmployeeUseCase."""

from __future__ import annotations

import pytest

from app.application.employees.create_employee import (
    CreateEmployeeCommand,
    CreateEmployeeUseCase,
)
from app.domain.employees.entities import Role
from app.domain.shared.exceptions import ConflictError
from app.infrastructure.auth import BcryptPasswordHasher
from tests.unit.application.fakes import FakeEmployeeRepository

pytestmark = pytest.mark.unit


@pytest.fixture
def use_case() -> CreateEmployeeUseCase:
    return CreateEmployeeUseCase(
        employee_repo=FakeEmployeeRepository(),
        password_hasher=BcryptPasswordHasher(),
    )


async def test_create_returns_employee_with_id(use_case: CreateEmployeeUseCase) -> None:
    result = await use_case.execute(
        CreateEmployeeCommand(
            email="new@x.com",
            full_name="Иван",
            role=Role.EMPLOYEE,
            initial_password="strong-pass",
        )
    )
    assert result.id > 0
    assert result.email == "new@x.com"
    assert result.role is Role.EMPLOYEE
    assert result.is_active is True
    # Хеш не равен plain.
    assert result.hashed_password != "strong-pass"


async def test_create_duplicate_email_raises_conflict(
    use_case: CreateEmployeeUseCase,
) -> None:
    await use_case.execute(
        CreateEmployeeCommand(
            email="dup@x.com",
            full_name="Первый",
            role=Role.EMPLOYEE,
            initial_password="p1234567",
        )
    )

    with pytest.raises(ConflictError) as exc_info:
        await use_case.execute(
            CreateEmployeeCommand(
                email="dup@x.com",
                full_name="Второй",
                role=Role.EMPLOYEE,
                initial_password="p1234567",
            )
        )
    assert exc_info.value.code == "employee_email_taken"
