"""Интеграционные тесты эндпоинта /api/v1/positioning/classify."""

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
from app.presentation.dependencies import _position_classifier_singleton
from app.presentation.middleware.rate_limit import limiter

pytestmark = pytest.mark.integration


_PASSWORD = "test-password-12345"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Сбрасываем slowapi и кеш classifier'а между тестами.

    Classifier — module-level singleton; lazy-обученная модель
    осталась бы между тестами и могла нарушить изоляцию (например,
    обучилась на старой fixture, потом тест ожидает 503 без данных).
    """
    limiter.reset()
    _position_classifier_singleton.cache_clear()


@pytest.fixture
async def seeded_calibration(
    db_engine: AsyncEngine,
) -> AsyncIterator[dict]:
    """Создаёт сотрудника + 2 зоны × 5 калибровочных точек.

    2 зоны с явно разделимыми RSSI-кластерами (центры -40 и -80 dBm).
    KNN с n_neighbors=3 должен корректно классифицировать observations
    у центров.
    """
    hasher = BcryptPasswordHasher()
    async with db_engine.begin() as conn:
        emp_result = await conn.execute(
            EmployeeORM.__table__.insert()
            .values(
                email="emp-pos@svetlyachok.local",
                full_name="Pos Tester",
                role=Role.EMPLOYEE,
                hashed_password=hasher.hash(_PASSWORD),
                is_active=True,
            )
            .returning(EmployeeORM.__table__.c.id)
        )
        emp_id = emp_result.scalar_one()

        zone1_result = await conn.execute(
            ZoneORM.__table__.insert()
            .values(name="Pos Zone Workplace", type=OrmZoneType.WORKPLACE)
            .returning(ZoneORM.__table__.c.id)
        )
        zone1_id = zone1_result.scalar_one()

        zone2_result = await conn.execute(
            ZoneORM.__table__.insert()
            .values(name="Pos Zone Outside", type=OrmZoneType.OUTSIDE_OFFICE)
            .returning(ZoneORM.__table__.c.id)
        )
        zone2_id = zone2_result.scalar_one()

        # 5 точек у zone1 (центр -40), 5 у zone2 (центр -80)
        for zid, center in [(zone1_id, -40), (zone2_id, -80)]:
            for i in range(5):
                await conn.execute(
                    FingerprintORM.__table__.insert().values(
                        employee_id=None,
                        zone_id=zid,
                        is_calibration=True,
                        captured_at=datetime.now(tz=UTC),
                        device_id="test-cal",
                        rssi_vector={
                            "AA:BB:CC:DD:EE:01": center + i,
                            "AA:BB:CC:DD:EE:02": center - 5,
                        },
                        sample_count=1,
                    )
                )

    yield {
        "employee": {
            "id": emp_id,
            "email": "emp-pos@svetlyachok.local",
            "password": _PASSWORD,
        },
        "zone_workplace_id": zone1_id,
        "zone_outside_id": zone2_id,
    }

    async with db_engine.begin() as conn:
        await conn.execute(
            delete(FingerprintORM).where(
                FingerprintORM.zone_id.in_([zone1_id, zone2_id])
            )
        )
        await conn.execute(
            delete(ZoneORM).where(ZoneORM.id.in_([zone1_id, zone2_id]))
        )
        await conn.execute(
            delete(EmployeeORM).where(EmployeeORM.email == "emp-pos@svetlyachok.local")
        )


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def test_classify_without_token_returns_401(
    client_with_db: AsyncClient,
) -> None:
    response = await client_with_db.post(
        "/api/v1/positioning/classify",
        json={"rssi_vector": {"AA:BB:CC:DD:EE:01": -45}},
    )
    assert response.status_code == 401


async def test_classify_empty_rssi_vector_rejected(
    client_with_db: AsyncClient,
    seeded_calibration: dict,
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_calibration["employee"]["email"]),
        str(seeded_calibration["employee"]["password"]),
    )
    response = await client_with_db.post(
        "/api/v1/positioning/classify",
        headers={"Authorization": f"Bearer {token}"},
        json={"rssi_vector": {}},
    )
    assert response.status_code in (400, 422)


async def test_classify_returns_correct_zone(
    client_with_db: AsyncClient,
    seeded_calibration: dict,
) -> None:
    """Observation у центра zone_workplace → predicted_zone == workplace."""
    token = await _login(
        client_with_db,
        str(seeded_calibration["employee"]["email"]),
        str(seeded_calibration["employee"]["password"]),
    )
    response = await client_with_db.post(
        "/api/v1/positioning/classify",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "rssi_vector": {
                "AA:BB:CC:DD:EE:01": -42,
                "AA:BB:CC:DD:EE:02": -45,
            }
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["zone_id"] == seeded_calibration["zone_workplace_id"]
    assert body["zone_type"] == "workplace"
    assert body["classifier_name"] == "wknn"
    assert 0.0 <= body["confidence"] <= 1.0


async def test_classify_returns_503_when_no_calibration(
    client_with_db: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Без калибровочных данных → 503 (training error proxied как
    classifier_not_ready или похожий код из exception handler)."""
    # Создаём только сотрудника, без зон и калибровки.
    hasher = BcryptPasswordHasher()
    async with db_engine.begin() as conn:
        await conn.execute(
            EmployeeORM.__table__.insert().values(
                email="lonely@svetlyachok.local",
                full_name="Lonely",
                role=Role.EMPLOYEE,
                hashed_password=hasher.hash(_PASSWORD),
                is_active=True,
            )
        )

    try:
        token = await _login(
            client_with_db, "lonely@svetlyachok.local", _PASSWORD
        )
        response = await client_with_db.post(
            "/api/v1/positioning/classify",
            headers={"Authorization": f"Bearer {token}"},
            json={"rssi_vector": {"AA:BB:CC:DD:EE:01": -45}},
        )
        # TrainingError → 503 (наследник AppError со status_code=503)
        assert response.status_code == 503
        body = response.json()
        # Конкретный code: empty_calibration_set (нет калибровочных данных)
        # Принимаем любой training-related code
        assert body["code"] in (
            "empty_calibration_set",
            "insufficient_calibration_points",
            "training_error",
        )
    finally:
        async with db_engine.begin() as conn:
            await conn.execute(
                delete(EmployeeORM).where(
                    EmployeeORM.email == "lonely@svetlyachok.local"
                )
            )
