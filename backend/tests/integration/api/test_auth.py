"""Интеграционные тесты эндпоинтов аутентификации."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.auth import BcryptPasswordHasher
from app.infrastructure.db.orm import Employee as EmployeeORM
from app.infrastructure.db.orm import Role
from app.presentation.middleware.rate_limit import limiter

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_TEST_PASSWORD = "test-password-12345"
_TEST_EMAIL = "auth-test@svetlyachok.local"


@pytest.fixture
async def seeded_employee(db_engine: AsyncEngine) -> AsyncIterator[dict[str, str]]:
    """Создаёт тестового активного сотрудника.

    Делаем INSERT через прямой connection (не savepoint), чтобы запись
    была видна параллельным сессиям FastAPI app. На teardown удаляем
    конкретного сотрудника по email.
    """
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash(_TEST_PASSWORD)

    async with db_engine.begin() as conn:
        await conn.execute(
            EmployeeORM.__table__.insert().values(
                email=_TEST_EMAIL,
                full_name="Test Employee",
                role=Role.EMPLOYEE,
                hashed_password=hashed,
                is_active=True,
            )
        )

    yield {"email": _TEST_EMAIL, "password": _TEST_PASSWORD}

    async with db_engine.begin() as conn:
        await conn.execute(delete(EmployeeORM).where(EmployeeORM.email == _TEST_EMAIL))


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Сбрасываем slowapi storage между тестами, иначе предыдущий тест
    оставит счётчик > 0 и rate-limit-тест завалится."""
    limiter.reset()


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


async def test_login_success_returns_token_pair(
    client_with_db: AsyncClient,
    seeded_employee: dict[str, str],
) -> None:
    response = await client_with_db.post(
        "/api/v1/auth/login",
        json={
            "email": seeded_employee["email"],
            "password": seeded_employee["password"],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


async def test_login_wrong_password_returns_401(
    client_with_db: AsyncClient,
    seeded_employee: dict[str, str],
) -> None:
    response = await client_with_db.post(
        "/api/v1/auth/login",
        json={"email": seeded_employee["email"], "password": "wrong-password"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "invalid_credentials"


async def test_login_unknown_email_returns_same_401(
    client_with_db: AsyncClient,
    seeded_employee: dict[str, str],
) -> None:
    """Неизвестный email и неверный пароль возвращают одинаковый ответ —
    защита от user enumeration."""
    response = await client_with_db.post(
        "/api/v1/auth/login",
        json={"email": "ghost@svetlyachok.local", "password": "any"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "invalid_credentials"


async def test_login_invalid_email_format_returns_400(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "12345678"},
    )
    # Pydantic validation → 422 Unprocessable Entity (FastAPI default).
    # Exception handler преобразует RequestValidationError в RFC 7807 400.
    assert response.status_code in (400, 422)


async def test_login_short_password_rejected_by_validation(
    client_with_db: AsyncClient,
) -> None:
    """min_length=8 в LoginRequest должен срабатывать."""
    response = await client_with_db.post(
        "/api/v1/auth/login",
        json={"email": "x@y.com", "password": "short"},
    )
    assert response.status_code in (400, 422)


async def test_login_extra_field_rejected(client_with_db: AsyncClient) -> None:
    """extra='forbid': нельзя пробросить is_admin=true."""
    response = await client_with_db.post(
        "/api/v1/auth/login",
        json={
            "email": "x@y.com",
            "password": "12345678",
            "is_admin": True,
        },
    )
    assert response.status_code in (400, 422)


async def test_login_rate_limit_kicks_in(
    client_with_db: AsyncClient,
    seeded_employee: dict[str, str],
) -> None:
    """5/minute → 6-й подряд должен быть 429."""
    payload = {"email": "ghost@svetlyachok.local", "password": "any"}

    statuses = []
    for _ in range(7):
        resp = await client_with_db.post("/api/v1/auth/login", json=payload)
        statuses.append(resp.status_code)

    # Первые 5 могут быть 401 (invalid_credentials), затем должны
    # появиться 429.
    assert 429 in statuses, f"rate limit не сработал, statuses={statuses}"


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------


async def test_refresh_success_returns_new_access(
    client_with_db: AsyncClient,
    seeded_employee: dict[str, str],
) -> None:
    # Сначала логинимся, чтобы получить refresh.
    login = await client_with_db.post(
        "/api/v1/auth/login",
        json=seeded_employee,
    )
    refresh_token = login.json()["refresh_token"]

    refresh = await client_with_db.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh.status_code == 200, refresh.text
    body = refresh.json()
    assert body["access_token"]
    # Refresh переиспользуется до истечения.
    assert body["refresh_token"] == refresh_token


async def test_refresh_invalid_token_returns_401(client_with_db: AsyncClient) -> None:
    response = await client_with_db.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not.a.real.jwt.at.all"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


async def test_refresh_with_access_token_returns_wrong_type(
    client_with_db: AsyncClient,
    seeded_employee: dict[str, str],
) -> None:
    """Подменить access как refresh нельзя."""
    login = await client_with_db.post("/api/v1/auth/login", json=seeded_employee)
    access_token = login.json()["access_token"]

    response = await client_with_db.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "wrong_token_type"
