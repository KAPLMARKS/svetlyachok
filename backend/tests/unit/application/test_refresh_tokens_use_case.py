"""Unit-тесты RefreshTokensUseCase."""

from __future__ import annotations

import pytest

from app.application.employees.refresh_tokens import (
    RefreshCommand,
    RefreshTokensUseCase,
)
from app.core.config import get_settings
from app.domain.employees.entities import Employee, Role
from app.domain.shared.exceptions import UnauthorizedError
from app.infrastructure.auth import BcryptPasswordHasher, JwtProvider

pytestmark = pytest.mark.unit


class FakeEmployeeRepository:
    def __init__(self, employees: list[Employee]) -> None:
        self._by_id = {e.id: e for e in employees}

    async def get_by_id(self, employee_id: int) -> Employee | None:
        return self._by_id.get(employee_id)

    async def get_by_email(self, email: str) -> Employee | None:  # pragma: no cover
        return None


@pytest.fixture
def hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


@pytest.fixture
def jwt_provider() -> JwtProvider:
    return JwtProvider(get_settings())


@pytest.fixture
def admin(hasher: BcryptPasswordHasher) -> Employee:
    return Employee(
        id=1,
        email="admin@x.com",
        full_name="Admin",
        role=Role.ADMIN,
        hashed_password=hasher.hash("password"),
        is_active=True,
    )


async def test_refresh_success_returns_new_token_pair(
    admin: Employee, jwt_provider: JwtProvider
) -> None:
    use_case = RefreshTokensUseCase(
        employee_repo=FakeEmployeeRepository([admin]),
        jwt_provider=jwt_provider,
    )

    refresh, _ = jwt_provider.encode_refresh_token(subject="1")

    pair = await use_case.execute(RefreshCommand(refresh_token=refresh))

    assert pair.access_token
    # Refresh переиспользуется до истечения — клиенту возвращаем тот же.
    assert pair.refresh_token == refresh
    # Новый access декодируется и содержит правильные claims.
    claims = jwt_provider.decode(pair.access_token, expected_type="access")
    assert claims.sub == "1"
    assert claims.role == "admin"


async def test_refresh_invalid_token_raises_unauthorized(
    admin: Employee, jwt_provider: JwtProvider
) -> None:
    use_case = RefreshTokensUseCase(
        employee_repo=FakeEmployeeRepository([admin]),
        jwt_provider=jwt_provider,
    )

    with pytest.raises(UnauthorizedError) as exc_info:
        await use_case.execute(RefreshCommand(refresh_token="not.a.jwt"))
    assert exc_info.value.code == "invalid_token"


async def test_refresh_with_access_token_raises_wrong_type(
    admin: Employee, jwt_provider: JwtProvider
) -> None:
    """Подменить access как refresh нельзя."""
    use_case = RefreshTokensUseCase(
        employee_repo=FakeEmployeeRepository([admin]),
        jwt_provider=jwt_provider,
    )

    access, _ = jwt_provider.encode_access_token(subject="1", role="admin")

    with pytest.raises(UnauthorizedError) as exc_info:
        await use_case.execute(RefreshCommand(refresh_token=access))
    assert exc_info.value.code == "wrong_token_type"


async def test_refresh_user_not_found_raises_unauthorized(
    jwt_provider: JwtProvider,
) -> None:
    """Refresh ссылается на удалённого пользователя."""
    use_case = RefreshTokensUseCase(
        employee_repo=FakeEmployeeRepository([]),
        jwt_provider=jwt_provider,
    )

    refresh, _ = jwt_provider.encode_refresh_token(subject="999")

    with pytest.raises(UnauthorizedError) as exc_info:
        await use_case.execute(RefreshCommand(refresh_token=refresh))
    assert exc_info.value.code == "user_not_found"


async def test_refresh_disabled_user_raises_unauthorized(
    hasher: BcryptPasswordHasher, jwt_provider: JwtProvider
) -> None:
    """Если пользователь деактивирован после выпуска refresh — нельзя
    обменять токен на новый."""
    disabled = Employee(
        id=5,
        email="x@x.com",
        full_name="X",
        role=Role.EMPLOYEE,
        hashed_password=hasher.hash("p"),
        is_active=False,
    )
    use_case = RefreshTokensUseCase(
        employee_repo=FakeEmployeeRepository([disabled]),
        jwt_provider=jwt_provider,
    )

    refresh, _ = jwt_provider.encode_refresh_token(subject="5")

    with pytest.raises(UnauthorizedError) as exc_info:
        await use_case.execute(RefreshCommand(refresh_token=refresh))
    assert exc_info.value.code == "user_disabled"
