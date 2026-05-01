"""Интеграционные тесты эндпоинтов /api/v1/attendance + интеграция с /classify."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.auth import BcryptPasswordHasher
from app.infrastructure.db.orm import AttendanceLog as AttendanceLogORM
from app.infrastructure.db.orm import Employee as EmployeeORM
from app.infrastructure.db.orm import Fingerprint as FingerprintORM
from app.infrastructure.db.orm import Role
from app.infrastructure.db.orm import Zone as ZoneORM
from app.infrastructure.db.orm.zones import ZoneType as OrmZoneType
from app.presentation.dependencies import _position_classifier_singleton
from app.presentation.middleware.rate_limit import limiter

pytestmark = pytest.mark.integration

_PASSWORD = "test-password-12345"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Сбрасываем slowapi и кеш classifier'а между тестами."""
    limiter.reset()
    _position_classifier_singleton.cache_clear()


@pytest.fixture
async def seeded_attendance_data(
    db_engine: AsyncEngine,
) -> AsyncIterator[dict]:
    """Создаёт admin + 2 employee + 2 зоны (workplace, corridor) + калибровку.

    Калибровка нужна, чтобы /classify работал и автоматически создавал
    AttendanceLog. Используем чёткие RSSI-кластеры -40 (workplace) и -80
    (corridor) для надёжной классификации.
    """
    hasher = BcryptPasswordHasher()
    async with db_engine.begin() as conn:
        # Сотрудники
        admin_result = await conn.execute(
            EmployeeORM.__table__.insert()
            .values(
                email="admin-att@svetlyachok.local",
                full_name="Admin Att",
                role=Role.ADMIN,
                hashed_password=hasher.hash(_PASSWORD),
                is_active=True,
                schedule_start=time(9, 0),
                schedule_end=time(18, 0),
            )
            .returning(EmployeeORM.__table__.c.id)
        )
        admin_id = admin_result.scalar_one()

        emp_a_result = await conn.execute(
            EmployeeORM.__table__.insert()
            .values(
                email="empa-att@svetlyachok.local",
                full_name="Emp A",
                role=Role.EMPLOYEE,
                hashed_password=hasher.hash(_PASSWORD),
                is_active=True,
                schedule_start=time(9, 0),
                schedule_end=time(18, 0),
            )
            .returning(EmployeeORM.__table__.c.id)
        )
        emp_a_id = emp_a_result.scalar_one()

        emp_b_result = await conn.execute(
            EmployeeORM.__table__.insert()
            .values(
                email="empb-att@svetlyachok.local",
                full_name="Emp B",
                role=Role.EMPLOYEE,
                hashed_password=hasher.hash(_PASSWORD),
                is_active=True,
                schedule_start=time(9, 0),
                schedule_end=time(18, 0),
            )
            .returning(EmployeeORM.__table__.c.id)
        )
        emp_b_id = emp_b_result.scalar_one()

        # Зоны
        wp_result = await conn.execute(
            ZoneORM.__table__.insert()
            .values(name="Att Workplace", type=OrmZoneType.WORKPLACE)
            .returning(ZoneORM.__table__.c.id)
        )
        workplace_id = wp_result.scalar_one()

        cr_result = await conn.execute(
            ZoneORM.__table__.insert()
            .values(name="Att Corridor", type=OrmZoneType.CORRIDOR)
            .returning(ZoneORM.__table__.c.id)
        )
        corridor_id = cr_result.scalar_one()

        # Калибровка: 5 точек на каждую зону.
        for zid, center in [(workplace_id, -40), (corridor_id, -80)]:
            for i in range(5):
                await conn.execute(
                    FingerprintORM.__table__.insert().values(
                        employee_id=None,
                        zone_id=zid,
                        is_calibration=True,
                        captured_at=datetime.now(tz=UTC),
                        device_id="att-cal",
                        rssi_vector={
                            "AA:BB:CC:DD:EE:01": center + i,
                            "AA:BB:CC:DD:EE:02": center - 5,
                        },
                        sample_count=1,
                    )
                )

    yield {
        "admin": {"id": admin_id, "email": "admin-att@svetlyachok.local"},
        "emp_a": {"id": emp_a_id, "email": "empa-att@svetlyachok.local"},
        "emp_b": {"id": emp_b_id, "email": "empb-att@svetlyachok.local"},
        "workplace_id": workplace_id,
        "corridor_id": corridor_id,
        "password": _PASSWORD,
    }

    async with db_engine.begin() as conn:
        await conn.execute(
            delete(AttendanceLogORM).where(
                AttendanceLogORM.employee_id.in_([admin_id, emp_a_id, emp_b_id])
            )
        )
        await conn.execute(
            delete(FingerprintORM).where(
                FingerprintORM.zone_id.in_([workplace_id, corridor_id])
            )
        )
        await conn.execute(
            delete(ZoneORM).where(ZoneORM.id.in_([workplace_id, corridor_id]))
        )
        await conn.execute(
            delete(EmployeeORM).where(
                EmployeeORM.id.in_([admin_id, emp_a_id, emp_b_id])
            )
        )


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def test_classify_creates_attendance_log_visible_via_list(
    client_with_db: AsyncClient,
    seeded_attendance_data: dict,
) -> None:
    """После /classify GET /attendance должен показать новую открытую сессию."""
    token = await _login(
        client_with_db,
        seeded_attendance_data["emp_a"]["email"],
        seeded_attendance_data["password"],
    )
    classify_response = await client_with_db.post(
        "/api/v1/positioning/classify",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "rssi_vector": {
                "AA:BB:CC:DD:EE:01": -42,
                "AA:BB:CC:DD:EE:02": -45,
            }
        },
    )
    assert classify_response.status_code == 200, classify_response.text
    assert classify_response.json()["zone_id"] == seeded_attendance_data["workplace_id"]

    # Дать пару миллисекунд на async-flush.
    list_response = await client_with_db.get(
        "/api/v1/attendance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200, list_response.text
    body = list_response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["employee_id"] == seeded_attendance_data["emp_a"]["id"]
    assert item["zone_id"] == seeded_attendance_data["workplace_id"]
    assert item["ended_at"] is None  # открытая сессия
    assert item["duration_seconds"] is None


async def test_zone_change_closes_previous_and_opens_new(
    client_with_db: AsyncClient,
    seeded_attendance_data: dict,
) -> None:
    """Два /classify в разные зоны → 2 сессии, первая закрыта."""
    token = await _login(
        client_with_db,
        seeded_attendance_data["emp_a"]["email"],
        seeded_attendance_data["password"],
    )
    # 1) Workplace
    r1 = await client_with_db.post(
        "/api/v1/positioning/classify",
        headers={"Authorization": f"Bearer {token}"},
        json={"rssi_vector": {"AA:BB:CC:DD:EE:01": -42, "AA:BB:CC:DD:EE:02": -45}},
    )
    assert r1.status_code == 200
    assert r1.json()["zone_id"] == seeded_attendance_data["workplace_id"]

    # 2) Corridor — разница во времени между запросами достаточна для duration > 0
    r2 = await client_with_db.post(
        "/api/v1/positioning/classify",
        headers={"Authorization": f"Bearer {token}"},
        json={"rssi_vector": {"AA:BB:CC:DD:EE:01": -82, "AA:BB:CC:DD:EE:02": -85}},
    )
    assert r2.status_code == 200
    assert r2.json()["zone_id"] == seeded_attendance_data["corridor_id"]

    list_response = await client_with_db.get(
        "/api/v1/attendance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 2

    closed = next(item for item in body["items"] if item["ended_at"] is not None)
    open_ = next(item for item in body["items"] if item["ended_at"] is None)
    assert closed["zone_id"] == seeded_attendance_data["workplace_id"]
    assert closed["duration_seconds"] is not None and closed["duration_seconds"] >= 0
    assert open_["zone_id"] == seeded_attendance_data["corridor_id"]


async def test_employee_cannot_see_other_employee_logs(
    client_with_db: AsyncClient,
    seeded_attendance_data: dict,
) -> None:
    """Employee A не может смотреть логи employee B → 403."""
    token_a = await _login(
        client_with_db,
        seeded_attendance_data["emp_a"]["email"],
        seeded_attendance_data["password"],
    )
    response = await client_with_db.get(
        "/api/v1/attendance",
        headers={"Authorization": f"Bearer {token_a}"},
        params={"employee_id": seeded_attendance_data["emp_b"]["id"]},
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "attendance_self_only"


async def test_admin_can_see_any_employee_logs(
    client_with_db: AsyncClient,
    seeded_attendance_data: dict,
    db_engine: AsyncEngine,
) -> None:
    """Admin видит логи любого сотрудника по фильтру."""
    # Засеем 2 закрытые сессии для emp_a напрямую в БД.
    base = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)
    async with db_engine.begin() as conn:
        for i in range(2):
            await conn.execute(
                AttendanceLogORM.__table__.insert().values(
                    employee_id=seeded_attendance_data["emp_a"]["id"],
                    zone_id=seeded_attendance_data["workplace_id"],
                    started_at=base.replace(hour=9 + i),
                    ended_at=base.replace(hour=10 + i),
                    last_seen_at=base.replace(hour=10 + i),
                    duration_seconds=3600,
                    status="present",
                )
            )

    admin_token = await _login(
        client_with_db,
        seeded_attendance_data["admin"]["email"],
        seeded_attendance_data["password"],
    )
    response = await client_with_db.get(
        "/api/v1/attendance",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"employee_id": seeded_attendance_data["emp_a"]["id"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2


async def test_summary_aggregates_work_hours_for_workplace_only(
    client_with_db: AsyncClient,
    seeded_attendance_data: dict,
    db_engine: AsyncEngine,
) -> None:
    """Засеваем 3 сессии (2 в workplace, 1 в corridor) → work_hours_total = 2.0."""
    base = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)
    async with db_engine.begin() as conn:
        # 1 час workplace
        await conn.execute(
            AttendanceLogORM.__table__.insert().values(
                employee_id=seeded_attendance_data["emp_a"]["id"],
                zone_id=seeded_attendance_data["workplace_id"],
                started_at=base,
                ended_at=base + timedelta(hours=1),
                last_seen_at=base + timedelta(hours=1),
                duration_seconds=3600,
                status="present",
            )
        )
        # 1 час workplace на следующий день
        await conn.execute(
            AttendanceLogORM.__table__.insert().values(
                employee_id=seeded_attendance_data["emp_a"]["id"],
                zone_id=seeded_attendance_data["workplace_id"],
                started_at=base + timedelta(days=1),
                ended_at=base + timedelta(days=1, hours=1),
                last_seen_at=base + timedelta(days=1, hours=1),
                duration_seconds=3600,
                status="present",
            )
        )
        # 1 час corridor — НЕ должен попасть в work_hours_total
        await conn.execute(
            AttendanceLogORM.__table__.insert().values(
                employee_id=seeded_attendance_data["emp_a"]["id"],
                zone_id=seeded_attendance_data["corridor_id"],
                started_at=base + timedelta(days=2),
                ended_at=base + timedelta(days=2, hours=1),
                last_seen_at=base + timedelta(days=2, hours=1),
                duration_seconds=3600,
                status="present",
            )
        )

    token_a = await _login(
        client_with_db,
        seeded_attendance_data["emp_a"]["email"],
        seeded_attendance_data["password"],
    )
    response = await client_with_db.get(
        "/api/v1/attendance/summary",
        headers={"Authorization": f"Bearer {token_a}"},
        params={
            "employee_id": seeded_attendance_data["emp_a"]["id"],
            "from": "2026-05-01T00:00:00+00:00",
            "to": "2026-05-31T23:59:59+00:00",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["work_hours_total"] == 2.0
    assert body["sessions_count"] == 3


async def test_unauthenticated_request_returns_401(
    client_with_db: AsyncClient,
    seeded_attendance_data: dict,
) -> None:
    """GET /attendance без токена → 401."""
    response = await client_with_db.get("/api/v1/attendance")
    assert response.status_code == 401
