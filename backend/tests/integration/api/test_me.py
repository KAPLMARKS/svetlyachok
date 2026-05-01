"""Интеграционные тесты GET /api/v1/me — защищённый эндпоинт."""

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


_TEST_PASSWORD = "test-password-12345"
_TEST_EMAIL = "me-test@svetlyachok.local"


@pytest.fixture
async def seeded_employee(db_engine: AsyncEngine) -> AsyncIterator[dict[str, str]]:
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash(_TEST_PASSWORD)

    async with db_engine.begin() as conn:
        await conn.execute(
            EmployeeORM.__table__.insert().values(
                email=_TEST_EMAIL,
                full_name="Me Tester",
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
    limiter.reset()


async def test_me_without_token_returns_401(client_with_db: AsyncClient) -> None:
    response = await client_with_db.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["code"] == "missing_token"


async def test_me_with_valid_token_returns_user(
    client_with_db: AsyncClient,
    seeded_employee: dict[str, str],
) -> None:
    login = await client_with_db.post("/api/v1/auth/login", json=seeded_employee)
    access = login.json()["access_token"]

    response = await client_with_db.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == seeded_employee["email"]
    assert body["full_name"] == "Me Tester"
    assert body["role"] == "employee"
    assert body["is_active"] is True
    # Hashed_password в ответе быть не должно.
    assert "hashed_password" not in body


async def test_me_with_invalid_token_returns_401(client_with_db: AsyncClient) -> None:
    response = await client_with_db.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer not.a.real.jwt"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


async def test_me_with_non_bearer_scheme_returns_401(
    client_with_db: AsyncClient,
) -> None:
    """Только Bearer-схема, никакой Basic/Digest."""
    response = await client_with_db.get(
        "/api/v1/me",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "missing_token"
