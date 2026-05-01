"""Интеграционные тесты эндпоинтов /api/v1/employees."""

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


_ADMIN_PASSWORD = "admin-password-12345"
_EMPLOYEE_PASSWORD = "employee-password-12345"


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    limiter.reset()


@pytest.fixture
async def seeded_users(
    db_engine: AsyncEngine,
) -> AsyncIterator[dict[str, dict[str, str | int]]]:
    """Создаёт admin'а и обычного employee."""
    hasher = BcryptPasswordHasher()
    async with db_engine.begin() as conn:
        admin_result = await conn.execute(
            EmployeeORM.__table__.insert().values(
                email="admin-crud@svetlyachok.local",
                full_name="Admin CRUD",
                role=Role.ADMIN,
                hashed_password=hasher.hash(_ADMIN_PASSWORD),
                is_active=True,
            ).returning(EmployeeORM.__table__.c.id)
        )
        admin_id = admin_result.scalar_one()

        emp_result = await conn.execute(
            EmployeeORM.__table__.insert().values(
                email="emp-crud@svetlyachok.local",
                full_name="Employee CRUD",
                role=Role.EMPLOYEE,
                hashed_password=hasher.hash(_EMPLOYEE_PASSWORD),
                is_active=True,
            ).returning(EmployeeORM.__table__.c.id)
        )
        emp_id = emp_result.scalar_one()

    yield {
        "admin": {
            "id": admin_id,
            "email": "admin-crud@svetlyachok.local",
            "password": _ADMIN_PASSWORD,
        },
        "employee": {
            "id": emp_id,
            "email": "emp-crud@svetlyachok.local",
            "password": _EMPLOYEE_PASSWORD,
        },
    }

    async with db_engine.begin() as conn:
        await conn.execute(
            delete(EmployeeORM).where(
                EmployeeORM.email.in_(
                    [
                        "admin-crud@svetlyachok.local",
                        "emp-crud@svetlyachok.local",
                        "new-emp@svetlyachok.local",  # созданный в test_create
                    ]
                )
            )
        )


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _admin_token(
    client: AsyncClient, seeded_users: dict[str, dict[str, str | int]]
) -> str:
    return await _login(
        client,
        str(seeded_users["admin"]["email"]),
        str(seeded_users["admin"]["password"]),
    )


async def _employee_token(
    client: AsyncClient, seeded_users: dict[str, dict[str, str | int]]
) -> str:
    return await _login(
        client,
        str(seeded_users["employee"]["email"]),
        str(seeded_users["employee"]["password"]),
    )


# ---------------------------------------------------------------------------
# POST /employees
# ---------------------------------------------------------------------------


async def test_create_employee_admin_success(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _admin_token(client_with_db, seeded_users)
    response = await client_with_db.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": "new-emp@svetlyachok.local",
            "full_name": "Новый",
            "role": "employee",
            "initial_password": "temp-pass-12345",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "new-emp@svetlyachok.local"
    assert body["role"] == "employee"
    assert "hashed_password" not in body


async def test_create_employee_by_non_admin_returns_403(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _employee_token(client_with_db, seeded_users)
    response = await client_with_db.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": "ghost@x.com",
            "full_name": "G",
            "role": "employee",
            "initial_password": "12345678",
        },
    )
    assert response.status_code == 403


async def test_create_duplicate_email_returns_409(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _admin_token(client_with_db, seeded_users)
    response = await client_with_db.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": str(seeded_users["admin"]["email"]),
            "full_name": "Dup",
            "role": "employee",
            "initial_password": "12345678",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "employee_email_taken"


# ---------------------------------------------------------------------------
# GET /employees and /employees/{id}
# ---------------------------------------------------------------------------


async def test_list_employees_admin(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _admin_token(client_with_db, seeded_users)
    response = await client_with_db.get(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    assert all("hashed_password" not in item for item in body["items"])


async def test_list_employees_non_admin_403(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _employee_token(client_with_db, seeded_users)
    response = await client_with_db.get(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_get_employee_self(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _employee_token(client_with_db, seeded_users)
    emp_id = seeded_users["employee"]["id"]
    response = await client_with_db.get(
        f"/api/v1/employees/{emp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


async def test_get_other_employee_forbidden(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    """Employee пытается посмотреть admin'а — 403."""
    token = await _employee_token(client_with_db, seeded_users)
    admin_id = seeded_users["admin"]["id"]
    response = await client_with_db.get(
        f"/api/v1/employees/{admin_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /employees/{id}
# ---------------------------------------------------------------------------


async def test_admin_can_change_role(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _admin_token(client_with_db, seeded_users)
    emp_id = seeded_users["employee"]["id"]
    response = await client_with_db.patch(
        f"/api/v1/employees/{emp_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_self_can_change_full_name_only(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _employee_token(client_with_db, seeded_users)
    emp_id = seeded_users["employee"]["id"]
    response = await client_with_db.patch(
        f"/api/v1/employees/{emp_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Самозаменён"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Самозаменён"


async def test_self_cannot_change_role(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _employee_token(client_with_db, seeded_users)
    emp_id = seeded_users["employee"]["id"]
    response = await client_with_db.patch(
        f"/api/v1/employees/{emp_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "cannot_modify_admin_fields"


# ---------------------------------------------------------------------------
# POST /employees/{id}/password
# ---------------------------------------------------------------------------


async def test_admin_resets_other_password_without_old(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _admin_token(client_with_db, seeded_users)
    emp_id = seeded_users["employee"]["id"]
    response = await client_with_db.post(
        f"/api/v1/employees/{emp_id}/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": "fresh-new-password"},
    )
    assert response.status_code == 200


async def test_self_changes_password_with_correct_old(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _employee_token(client_with_db, seeded_users)
    emp_id = seeded_users["employee"]["id"]
    response = await client_with_db.post(
        f"/api/v1/employees/{emp_id}/password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "old_password": _EMPLOYEE_PASSWORD,
            "new_password": "another-fresh-pass",
        },
    )
    assert response.status_code == 200


async def test_self_change_password_wrong_old_returns_401(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _employee_token(client_with_db, seeded_users)
    emp_id = seeded_users["employee"]["id"]
    response = await client_with_db.post(
        f"/api/v1/employees/{emp_id}/password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "old_password": "wrong-old",
            "new_password": "new-pass-12345",
        },
    )
    assert response.status_code == 401
    assert response.json()["code"] == "wrong_old_password"


# ---------------------------------------------------------------------------
# Deactivate / Activate
# ---------------------------------------------------------------------------


async def test_admin_cannot_deactivate_self(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _admin_token(client_with_db, seeded_users)
    admin_id = seeded_users["admin"]["id"]
    response = await client_with_db.post(
        f"/api/v1/employees/{admin_id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "cannot_deactivate_self"


async def test_admin_deactivates_other_then_activates(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _admin_token(client_with_db, seeded_users)
    emp_id = seeded_users["employee"]["id"]

    deact = await client_with_db.post(
        f"/api/v1/employees/{emp_id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    # После деактивации login этого пользователя должен ломаться
    # (LoginUseCase проверяет is_active).
    failed_login = await client_with_db.post(
        "/api/v1/auth/login",
        json={
            "email": str(seeded_users["employee"]["email"]),
            "password": _EMPLOYEE_PASSWORD,
        },
    )
    assert failed_login.status_code == 401

    # Реактивация
    act = await client_with_db.post(
        f"/api/v1/employees/{emp_id}/activate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert act.status_code == 200
    assert act.json()["is_active"] is True
