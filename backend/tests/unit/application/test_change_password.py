"""Unit-тесты ChangePasswordUseCase."""

from __future__ import annotations

import pytest

from app.application.employees.change_password import (
    ChangePasswordCommand,
    ChangePasswordUseCase,
)
from app.domain.employees.entities import Employee, Role
from app.domain.shared.exceptions import (
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.infrastructure.auth import BcryptPasswordHasher
from tests.unit.application.fakes import FakeEmployeeRepository

pytestmark = pytest.mark.unit


_OLD_PASSWORD = "old-password-123"
_NEW_PASSWORD = "new-password-456"


@pytest.fixture
async def repo_with_user() -> tuple[FakeEmployeeRepository, Employee, BcryptPasswordHasher]:
    hasher = BcryptPasswordHasher()
    repo = FakeEmployeeRepository()
    user = await repo.add(
        Employee(
            id=0,
            email="u@x.com",
            full_name="U",
            role=Role.EMPLOYEE,
            hashed_password=hasher.hash(_OLD_PASSWORD),
            is_active=True,
        )
    )
    return repo, user, hasher


async def test_admin_reset_changes_password_without_old(
    repo_with_user: tuple[FakeEmployeeRepository, Employee, BcryptPasswordHasher],
) -> None:
    repo, user, hasher = repo_with_user
    use_case = ChangePasswordUseCase(employee_repo=repo, password_hasher=hasher)

    result = await use_case.execute(
        ChangePasswordCommand(
            employee_id=user.id,
            new_password=_NEW_PASSWORD,
            is_admin_reset=True,
        )
    )

    assert hasher.verify(_NEW_PASSWORD, result.hashed_password)
    assert not hasher.verify(_OLD_PASSWORD, result.hashed_password)


async def test_self_change_with_correct_old_password(
    repo_with_user: tuple[FakeEmployeeRepository, Employee, BcryptPasswordHasher],
) -> None:
    repo, user, hasher = repo_with_user
    use_case = ChangePasswordUseCase(employee_repo=repo, password_hasher=hasher)

    result = await use_case.execute(
        ChangePasswordCommand(
            employee_id=user.id,
            new_password=_NEW_PASSWORD,
            old_password=_OLD_PASSWORD,
            is_admin_reset=False,
        )
    )

    assert hasher.verify(_NEW_PASSWORD, result.hashed_password)


async def test_self_change_with_wrong_old_password_raises(
    repo_with_user: tuple[FakeEmployeeRepository, Employee, BcryptPasswordHasher],
) -> None:
    repo, user, hasher = repo_with_user
    use_case = ChangePasswordUseCase(employee_repo=repo, password_hasher=hasher)

    with pytest.raises(UnauthorizedError) as exc_info:
        await use_case.execute(
            ChangePasswordCommand(
                employee_id=user.id,
                new_password=_NEW_PASSWORD,
                old_password="wrong-password",
                is_admin_reset=False,
            )
        )
    assert exc_info.value.code == "wrong_old_password"


async def test_self_change_without_old_raises_validation(
    repo_with_user: tuple[FakeEmployeeRepository, Employee, BcryptPasswordHasher],
) -> None:
    repo, user, hasher = repo_with_user
    use_case = ChangePasswordUseCase(employee_repo=repo, password_hasher=hasher)

    with pytest.raises(ValidationError) as exc_info:
        await use_case.execute(
            ChangePasswordCommand(
                employee_id=user.id,
                new_password=_NEW_PASSWORD,
                is_admin_reset=False,
            )
        )
    assert exc_info.value.code == "old_password_required"


async def test_change_password_unknown_id_raises_not_found(
    repo_with_user: tuple[FakeEmployeeRepository, Employee, BcryptPasswordHasher],
) -> None:
    repo, _, hasher = repo_with_user
    use_case = ChangePasswordUseCase(employee_repo=repo, password_hasher=hasher)

    with pytest.raises(NotFoundError):
        await use_case.execute(
            ChangePasswordCommand(
                employee_id=99999,
                new_password=_NEW_PASSWORD,
                is_admin_reset=True,
            )
        )
