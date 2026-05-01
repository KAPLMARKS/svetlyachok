"""Интеграционные тесты эндпоинтов /api/v1/calibration."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.auth import BcryptPasswordHasher
from app.infrastructure.db.orm import Employee as EmployeeORM
from app.infrastructure.db.orm import Fingerprint as FingerprintORM
from app.infrastructure.db.orm import Role
from app.infrastructure.db.orm import Zone as ZoneORM
from app.infrastructure.db.orm.zones import ZoneType as OrmZoneType
from app.presentation.middleware.rate_limit import limiter

pytestmark = pytest.mark.integration


_ADMIN_PASSWORD = "admin-password-12345"
_EMPLOYEE_PASSWORD = "employee-password-12345"


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    limiter.reset()


@pytest.fixture
async def seeded_users_and_zone(
    db_engine: AsyncEngine,
) -> AsyncIterator[dict[str, dict[str, str | int]]]:
    hasher = BcryptPasswordHasher()
    async with db_engine.begin() as conn:
        admin_result = await conn.execute(
            EmployeeORM.__table__.insert().values(
                email="admin-cal@svetlyachok.local",
                full_name="Admin Cal",
                role=Role.ADMIN,
                hashed_password=hasher.hash(_ADMIN_PASSWORD),
                is_active=True,
            ).returning(EmployeeORM.__table__.c.id)
        )
        admin_id = admin_result.scalar_one()
        emp_result = await conn.execute(
            EmployeeORM.__table__.insert().values(
                email="emp-cal@svetlyachok.local",
                full_name="Emp Cal",
                role=Role.EMPLOYEE,
                hashed_password=hasher.hash(_EMPLOYEE_PASSWORD),
                is_active=True,
            ).returning(EmployeeORM.__table__.c.id)
        )
        emp_id = emp_result.scalar_one()
        zone_result = await conn.execute(
            ZoneORM.__table__.insert().values(
                name="Cal Test Zone",
                type=OrmZoneType.WORKPLACE,
            ).returning(ZoneORM.__table__.c.id)
        )
        zone_id = zone_result.scalar_one()

    yield {
        "admin": {
            "id": admin_id,
            "email": "admin-cal@svetlyachok.local",
            "password": _ADMIN_PASSWORD,
        },
        "employee": {
            "id": emp_id,
            "email": "emp-cal@svetlyachok.local",
            "password": _EMPLOYEE_PASSWORD,
        },
        "zone_id": zone_id,
    }

    async with db_engine.begin() as conn:
        # Сначала fingerprints — у них FK SET NULL на zone_id, но это
        # не помешает удалению. Затем zones и employees.
        await conn.execute(
            delete(FingerprintORM).where(FingerprintORM.zone_id == zone_id)
        )
        await conn.execute(delete(ZoneORM).where(ZoneORM.id == zone_id))
        await conn.execute(
            delete(EmployeeORM).where(
                EmployeeORM.email.in_(
                    ["admin-cal@svetlyachok.local", "emp-cal@svetlyachok.local"]
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
# POST /calibration/points
# ---------------------------------------------------------------------------


async def test_create_calibration_admin_success(
    client_with_db: AsyncClient,
    seeded_users_and_zone: dict,
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_users_and_zone["admin"]["email"]),
        str(seeded_users_and_zone["admin"]["password"]),
    )
    response = await client_with_db.post(
        "/api/v1/calibration/points",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "zone_id": seeded_users_and_zone["zone_id"],
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": _vector(),
            "sample_count": 5,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["is_calibration"] is True
    assert body["zone_id"] == seeded_users_and_zone["zone_id"]


async def test_create_calibration_employee_403(
    client_with_db: AsyncClient,
    seeded_users_and_zone: dict,
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_users_and_zone["employee"]["email"]),
        str(seeded_users_and_zone["employee"]["password"]),
    )
    response = await client_with_db.post(
        "/api/v1/calibration/points",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "zone_id": seeded_users_and_zone["zone_id"],
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": _vector(),
        },
    )
    assert response.status_code == 403


async def test_create_calibration_unknown_zone_returns_404(
    client_with_db: AsyncClient,
    seeded_users_and_zone: dict,
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_users_and_zone["admin"]["email"]),
        str(seeded_users_and_zone["admin"]["password"]),
    )
    response = await client_with_db.post(
        "/api/v1/calibration/points",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "zone_id": 999999,
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": _vector(),
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "zone_not_found"


# ---------------------------------------------------------------------------
# GET /calibration/points
# ---------------------------------------------------------------------------


async def test_list_calibration_authenticated_employee(
    client_with_db: AsyncClient,
    seeded_users_and_zone: dict,
) -> None:
    """Любой авторизованный, в т.ч. employee, может видеть калибровочные точки."""
    # Создаём калибровочную точку через admin
    admin_token = await _login(
        client_with_db,
        str(seeded_users_and_zone["admin"]["email"]),
        str(seeded_users_and_zone["admin"]["password"]),
    )
    await client_with_db.post(
        "/api/v1/calibration/points",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "zone_id": seeded_users_and_zone["zone_id"],
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": _vector(),
        },
    )

    emp_token = await _login(
        client_with_db,
        str(seeded_users_and_zone["employee"]["email"]),
        str(seeded_users_and_zone["employee"]["password"]),
    )
    response = await client_with_db.get(
        "/api/v1/calibration/points",
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1


# ---------------------------------------------------------------------------
# DELETE /calibration/points/{id}
# ---------------------------------------------------------------------------


async def test_delete_calibration_admin_success(
    client_with_db: AsyncClient,
    seeded_users_and_zone: dict,
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_users_and_zone["admin"]["email"]),
        str(seeded_users_and_zone["admin"]["password"]),
    )
    create = await client_with_db.post(
        "/api/v1/calibration/points",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "zone_id": seeded_users_and_zone["zone_id"],
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": _vector(),
        },
    )
    fp_id = create.json()["id"]

    delete_resp = await client_with_db.delete(
        f"/api/v1/calibration/points/{fp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_resp.status_code == 204


async def test_delete_calibration_rejects_live_fingerprint(
    client_with_db: AsyncClient,
    seeded_users_and_zone: dict,
) -> None:
    """DELETE /calibration/points/{id} НЕ должен удалять live-отпечаток."""
    emp_token = await _login(
        client_with_db,
        str(seeded_users_and_zone["employee"]["email"]),
        str(seeded_users_and_zone["employee"]["password"]),
    )
    submit = await client_with_db.post(
        "/api/v1/fingerprints",
        headers={"Authorization": f"Bearer {emp_token}"},
        json={
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": _vector(),
        },
    )
    fp_id = submit.json()["id"]

    admin_token = await _login(
        client_with_db,
        str(seeded_users_and_zone["admin"]["email"]),
        str(seeded_users_and_zone["admin"]["password"]),
    )
    response = await client_with_db.delete(
        f"/api/v1/calibration/points/{fp_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "not_a_calibration_point"
