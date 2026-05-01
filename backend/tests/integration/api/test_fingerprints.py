"""Интеграционные тесты эндпоинтов /api/v1/fingerprints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.auth import BcryptPasswordHasher
from app.infrastructure.db.orm import Employee as EmployeeORM
from app.infrastructure.db.orm import Fingerprint as FingerprintORM
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
    hasher = BcryptPasswordHasher()
    async with db_engine.begin() as conn:
        admin_result = await conn.execute(
            EmployeeORM.__table__.insert().values(
                email="admin-fp@svetlyachok.local",
                full_name="Admin FP",
                role=Role.ADMIN,
                hashed_password=hasher.hash(_ADMIN_PASSWORD),
                is_active=True,
            ).returning(EmployeeORM.__table__.c.id)
        )
        admin_id = admin_result.scalar_one()
        emp_result = await conn.execute(
            EmployeeORM.__table__.insert().values(
                email="emp-fp@svetlyachok.local",
                full_name="Emp FP",
                role=Role.EMPLOYEE,
                hashed_password=hasher.hash(_EMPLOYEE_PASSWORD),
                is_active=True,
            ).returning(EmployeeORM.__table__.c.id)
        )
        emp_id = emp_result.scalar_one()

    yield {
        "admin": {
            "id": admin_id,
            "email": "admin-fp@svetlyachok.local",
            "password": _ADMIN_PASSWORD,
        },
        "employee": {
            "id": emp_id,
            "email": "emp-fp@svetlyachok.local",
            "password": _EMPLOYEE_PASSWORD,
        },
    }

    async with db_engine.begin() as conn:
        # Сначала удаляем fingerprints (FK на employees ondelete=SET NULL —
        # отпечатки бы остались с employee_id=NULL и засоряли БД).
        await conn.execute(
            delete(FingerprintORM).where(
                FingerprintORM.employee_id.in_([admin_id, emp_id])
            )
        )
        await conn.execute(
            delete(EmployeeORM).where(
                EmployeeORM.email.in_(
                    ["admin-fp@svetlyachok.local", "emp-fp@svetlyachok.local"]
                )
            )
        )


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _vector() -> dict[str, int]:
    return {"AA:BB:CC:DD:EE:01": -45, "AA:BB:CC:DD:EE:02": -67}


# ---------------------------------------------------------------------------
# POST /fingerprints
# ---------------------------------------------------------------------------


async def test_submit_fingerprint_employee_success(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_users["employee"]["email"]),
        str(seeded_users["employee"]["password"]),
    )
    response = await client_with_db.post(
        "/api/v1/fingerprints",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": _vector(),
            "sample_count": 3,
            "device_id": "test-device",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["employee_id"] == seeded_users["employee"]["id"]
    assert body["is_calibration"] is False
    assert body["zone_id"] is None
    assert body["sample_count"] == 3


async def test_submit_fingerprint_without_token_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(
        "/api/v1/fingerprints",
        json={
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": _vector(),
        },
    )
    assert response.status_code == 401


async def test_submit_fingerprint_future_captured_at_rejected(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_users["employee"]["email"]),
        str(seeded_users["employee"]["password"]),
    )
    far_future = datetime.now(tz=UTC) + timedelta(hours=2)
    response = await client_with_db.post(
        "/api/v1/fingerprints",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "captured_at": far_future.isoformat(),
            "rssi_vector": _vector(),
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "captured_at_in_future"


async def test_submit_fingerprint_empty_rssi_rejected(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_users["employee"]["email"]),
        str(seeded_users["employee"]["password"]),
    )
    response = await client_with_db.post(
        "/api/v1/fingerprints",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": {},
        },
    )
    # Pydantic min_length=1 → 400/422
    assert response.status_code in (400, 422)


# ---------------------------------------------------------------------------
# GET /fingerprints
# ---------------------------------------------------------------------------


async def test_list_fingerprints_admin(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    # Сначала employee submit'ит отпечаток
    emp_token = await _login(
        client_with_db,
        str(seeded_users["employee"]["email"]),
        str(seeded_users["employee"]["password"]),
    )
    await client_with_db.post(
        "/api/v1/fingerprints",
        headers={"Authorization": f"Bearer {emp_token}"},
        json={
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": _vector(),
        },
    )

    admin_token = await _login(
        client_with_db,
        str(seeded_users["admin"]["email"]),
        str(seeded_users["admin"]["password"]),
    )
    response = await client_with_db.get(
        "/api/v1/fingerprints",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1


async def test_list_fingerprints_employee_403(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_users["employee"]["email"]),
        str(seeded_users["employee"]["password"]),
    )
    response = await client_with_db.get(
        "/api/v1/fingerprints",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
