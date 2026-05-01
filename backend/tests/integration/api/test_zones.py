"""Интеграционные тесты эндпоинтов /api/v1/zones."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.auth import BcryptPasswordHasher
from app.infrastructure.db.orm import (
    AttendanceLog,
    AttendanceStatus,
    Role,
)
from app.infrastructure.db.orm import (
    Employee as EmployeeORM,
)
from app.infrastructure.db.orm import (
    Zone as ZoneORM,
)
from app.infrastructure.db.orm.zones import ZoneType as OrmZoneType
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
                email="admin-zones@svetlyachok.local",
                full_name="Admin Zones",
                role=Role.ADMIN,
                hashed_password=hasher.hash(_ADMIN_PASSWORD),
                is_active=True,
            ).returning(EmployeeORM.__table__.c.id)
        )
        admin_id = admin_result.scalar_one()
        emp_result = await conn.execute(
            EmployeeORM.__table__.insert().values(
                email="emp-zones@svetlyachok.local",
                full_name="Emp Zones",
                role=Role.EMPLOYEE,
                hashed_password=hasher.hash(_EMPLOYEE_PASSWORD),
                is_active=True,
            ).returning(EmployeeORM.__table__.c.id)
        )
        emp_id = emp_result.scalar_one()

    yield {
        "admin": {
            "id": admin_id,
            "email": "admin-zones@svetlyachok.local",
            "password": _ADMIN_PASSWORD,
        },
        "employee": {
            "id": emp_id,
            "email": "emp-zones@svetlyachok.local",
            "password": _EMPLOYEE_PASSWORD,
        },
    }

    async with db_engine.begin() as conn:
        await conn.execute(
            delete(EmployeeORM).where(
                EmployeeORM.email.in_(
                    [
                        "admin-zones@svetlyachok.local",
                        "emp-zones@svetlyachok.local",
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


async def test_create_zone_admin_success(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_users["admin"]["email"]),
        str(seeded_users["admin"]["password"]),
    )
    response = await client_with_db.post(
        "/api/v1/zones",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Тест Зона API",
            "type": "workplace",
            "description": "Описание",
            "display_color": "#4A90E2",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Тест Зона API"
    assert body["type"] == "workplace"


async def test_create_zone_non_admin_403(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_users["employee"]["email"]),
        str(seeded_users["employee"]["password"]),
    )
    response = await client_with_db.post(
        "/api/v1/zones",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "X", "type": "workplace"},
    )
    assert response.status_code == 403


async def test_create_zone_invalid_hex_returns_422(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_users["admin"]["email"]),
        str(seeded_users["admin"]["password"]),
    )
    response = await client_with_db.post(
        "/api/v1/zones",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Bad", "type": "workplace", "display_color": "red"},
    )
    assert response.status_code in (400, 422)


async def test_list_zones_authenticated_employee(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
    db_engine: AsyncEngine,
) -> None:
    """Любой авторизованный, в т.ч. employee, может видеть список зон."""
    # Создадим зону через ORM напрямую для изоляции от других тестов.
    async with db_engine.begin() as conn:
        await conn.execute(
            ZoneORM.__table__.insert().values(
                name="Зона для list test",
                type=OrmZoneType.MEETING_ROOM,
            )
        )
    try:
        token = await _login(
            client_with_db,
            str(seeded_users["employee"]["email"]),
            str(seeded_users["employee"]["password"]),
        )
        response = await client_with_db.get(
            "/api/v1/zones",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1
    finally:
        async with db_engine.begin() as conn:
            await conn.execute(
                delete(ZoneORM).where(ZoneORM.name == "Зона для list test")
            )


async def test_update_zone_admin(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
    db_engine: AsyncEngine,
) -> None:
    async with db_engine.begin() as conn:
        result = await conn.execute(
            ZoneORM.__table__.insert()
            .values(name="Update test", type=OrmZoneType.WORKPLACE)
            .returning(ZoneORM.__table__.c.id)
        )
        zone_id = result.scalar_one()
    try:
        token = await _login(
            client_with_db,
            str(seeded_users["admin"]["email"]),
            str(seeded_users["admin"]["password"]),
        )
        response = await client_with_db.patch(
            f"/api/v1/zones/{zone_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Updated test"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated test"
    finally:
        async with db_engine.begin() as conn:
            await conn.execute(delete(ZoneORM).where(ZoneORM.id == zone_id))


async def test_delete_zone_no_dependencies(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
    db_engine: AsyncEngine,
) -> None:
    async with db_engine.begin() as conn:
        result = await conn.execute(
            ZoneORM.__table__.insert()
            .values(name="Delete me", type=OrmZoneType.CORRIDOR)
            .returning(ZoneORM.__table__.c.id)
        )
        zone_id = result.scalar_one()
    token = await _login(
        client_with_db,
        str(seeded_users["admin"]["email"]),
        str(seeded_users["admin"]["password"]),
    )
    response = await client_with_db.delete(
        f"/api/v1/zones/{zone_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


async def test_delete_zone_in_use_returns_409(
    client_with_db: AsyncClient,
    seeded_users: dict[str, dict[str, str | int]],
    db_engine: AsyncEngine,
) -> None:
    """Если на зону ссылается attendance_log — DELETE → 409 zone_in_use."""
    async with db_engine.begin() as conn:
        zone_result = await conn.execute(
            ZoneORM.__table__.insert()
            .values(name="In use", type=OrmZoneType.WORKPLACE)
            .returning(ZoneORM.__table__.c.id)
        )
        zone_id = zone_result.scalar_one()

        await conn.execute(
            AttendanceLog.__table__.insert().values(
                employee_id=seeded_users["employee"]["id"],
                zone_id=zone_id,
                started_at=datetime.now(tz=UTC),
                status=AttendanceStatus.PRESENT,
            )
        )

    try:
        token = await _login(
            client_with_db,
            str(seeded_users["admin"]["email"]),
            str(seeded_users["admin"]["password"]),
        )
        response = await client_with_db.delete(
            f"/api/v1/zones/{zone_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409
        assert response.json()["code"] == "zone_in_use"
    finally:
        async with db_engine.begin() as conn:
            await conn.execute(
                delete(AttendanceLog).where(AttendanceLog.zone_id == zone_id)
            )
            await conn.execute(delete(ZoneORM).where(ZoneORM.id == zone_id))
