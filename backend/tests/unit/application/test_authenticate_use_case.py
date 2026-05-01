"""Unit-тесты LoginUseCase с in-memory fake'ами.

Проверяем:
- Успешный сценарий → TokenPair.
- 3 fail-сценария (no user / wrong password / inactive) → один и тот же
  UnauthorizedError(invalid_credentials) (защита от user enumeration).
- Timing-safety: время ответа на «нет пользователя» сопоставимо со
  «неверным паролем» (оба тратят bcrypt-цикл).
"""

from __future__ import annotations

import contextlib
import time

import pytest

from app.application.employees.authenticate import LoginCommand, LoginUseCase
from app.core.config import get_settings
from app.domain.employees.entities import Employee, Role
from app.domain.shared.exceptions import UnauthorizedError
from app.infrastructure.auth import BcryptPasswordHasher, JwtProvider

pytestmark = pytest.mark.unit


class FakeEmployeeRepository:
    """In-memory репозиторий для unit-тестов."""

    def __init__(self, employees: list[Employee]) -> None:
        self._by_email = {e.email: e for e in employees}
        self._by_id = {e.id: e for e in employees}

    async def get_by_id(self, employee_id: int) -> Employee | None:
        return self._by_id.get(employee_id)

    async def get_by_email(self, email: str) -> Employee | None:
        return self._by_email.get(email)


@pytest.fixture
def hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


@pytest.fixture
def jwt_provider() -> JwtProvider:
    return JwtProvider(get_settings())


@pytest.fixture
def admin_employee(hasher: BcryptPasswordHasher) -> Employee:
    return Employee(
        id=1,
        email="admin@x.com",
        full_name="Admin",
        role=Role.ADMIN,
        hashed_password=hasher.hash("admin-password"),
        is_active=True,
    )


@pytest.fixture
def inactive_employee(hasher: BcryptPasswordHasher) -> Employee:
    return Employee(
        id=2,
        email="disabled@x.com",
        full_name="Disabled",
        role=Role.EMPLOYEE,
        hashed_password=hasher.hash("disabled-password"),
        is_active=False,
    )


async def test_login_success_returns_token_pair(
    admin_employee: Employee,
    hasher: BcryptPasswordHasher,
    jwt_provider: JwtProvider,
) -> None:
    use_case = LoginUseCase(
        employee_repo=FakeEmployeeRepository([admin_employee]),
        password_hasher=hasher,
        jwt_provider=jwt_provider,
    )

    pair = await use_case.execute(
        LoginCommand(email="admin@x.com", password="admin-password")
    )

    assert pair.access_token
    assert pair.refresh_token
    assert pair.expires_in > 0
    # Можем разкодировать access и убедиться, что role/sub те, что нужно.
    claims = jwt_provider.decode(pair.access_token, expected_type="access")
    assert claims.sub == "1"
    assert claims.role == "admin"


async def test_login_unknown_email_raises_invalid_credentials(
    hasher: BcryptPasswordHasher,
    jwt_provider: JwtProvider,
) -> None:
    use_case = LoginUseCase(
        employee_repo=FakeEmployeeRepository([]),
        password_hasher=hasher,
        jwt_provider=jwt_provider,
    )

    with pytest.raises(UnauthorizedError) as exc_info:
        await use_case.execute(LoginCommand(email="ghost@x.com", password="any"))
    assert exc_info.value.code == "invalid_credentials"


async def test_login_wrong_password_raises_invalid_credentials(
    admin_employee: Employee,
    hasher: BcryptPasswordHasher,
    jwt_provider: JwtProvider,
) -> None:
    use_case = LoginUseCase(
        employee_repo=FakeEmployeeRepository([admin_employee]),
        password_hasher=hasher,
        jwt_provider=jwt_provider,
    )

    with pytest.raises(UnauthorizedError) as exc_info:
        await use_case.execute(
            LoginCommand(email="admin@x.com", password="wrong-password")
        )
    assert exc_info.value.code == "invalid_credentials"


async def test_login_inactive_user_raises_invalid_credentials(
    inactive_employee: Employee,
    hasher: BcryptPasswordHasher,
    jwt_provider: JwtProvider,
) -> None:
    """Деактивированный пользователь не должен мочь войти; код такой же,
    как при неверном пароле, чтобы не дать enumerate'ить."""
    use_case = LoginUseCase(
        employee_repo=FakeEmployeeRepository([inactive_employee]),
        password_hasher=hasher,
        jwt_provider=jwt_provider,
    )

    with pytest.raises(UnauthorizedError) as exc_info:
        await use_case.execute(
            LoginCommand(email="disabled@x.com", password="disabled-password")
        )
    assert exc_info.value.code == "invalid_credentials"


async def test_login_timing_safe_for_unknown_user(
    admin_employee: Employee,
    hasher: BcryptPasswordHasher,
    jwt_provider: JwtProvider,
) -> None:
    """Время ответа на «нет пользователя» должно быть сопоставимо со
    временем «неверный пароль». Допускаем разброс до 2x — bcrypt
    нестабилен по таймингам, но порядок одинаковый.
    """
    use_case = LoginUseCase(
        employee_repo=FakeEmployeeRepository([admin_employee]),
        password_hasher=hasher,
        jwt_provider=jwt_provider,
    )

    async def _measure(email: str) -> float:
        start = time.perf_counter()
        with contextlib.suppress(UnauthorizedError):
            await use_case.execute(LoginCommand(email=email, password="wrong-password"))
        return time.perf_counter() - start

    t_unknown = await _measure("ghost@x.com")
    t_wrong_pass = await _measure("admin@x.com")

    # Оба должны быть в пределах одного порядка. Bcrypt со work_factor=12
    # это ~250 мс на современном железе; разброс до 2x — норма.
    ratio = max(t_unknown, t_wrong_pass) / max(min(t_unknown, t_wrong_pass), 0.001)
    assert ratio < 2.0, (
        f"Timing-leak: ratio={ratio:.2f}, "
        f"unknown={t_unknown:.3f}s, wrong_pass={t_wrong_pass:.3f}s"
    )
