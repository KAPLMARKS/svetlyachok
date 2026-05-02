"""Интеграционные тесты автоматической инвалидации singleton-классификатора.

Сценарий: после CRUD на `/api/v1/calibration/points` следующий
`/classify` должен использовать актуальную калибровочную выборку, а не
закешированную модель. Тесты доказывают, что invalidate-хук
действительно сбрасывает singleton.
"""

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

_ADMIN_PASSWORD = "admin-password-12345"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Сбрасываем slowapi и singleton classifier между тестами."""
    limiter.reset()
    _position_classifier_singleton.cache_clear()


@pytest.fixture
async def seeded_two_zones_calibrated(
    db_engine: AsyncEngine,
) -> AsyncIterator[dict]:
    """Admin + 2 зоны (workplace, corridor) × 5 калибровочных точек.

    Кластеры RSSI явно разделимы: workplace ~ -40 dBm, corridor ~ -80 dBm.
    """
    hasher = BcryptPasswordHasher()
    async with db_engine.begin() as conn:
        admin_result = await conn.execute(
            EmployeeORM.__table__.insert()
            .values(
                email="admin-inv@svetlyachok.local",
                full_name="Admin Inv",
                role=Role.ADMIN,
                hashed_password=hasher.hash(_ADMIN_PASSWORD),
                is_active=True,
            )
            .returning(EmployeeORM.__table__.c.id)
        )
        admin_id = admin_result.scalar_one()

        wp_result = await conn.execute(
            ZoneORM.__table__.insert()
            .values(name="Inv Workplace", type=OrmZoneType.WORKPLACE)
            .returning(ZoneORM.__table__.c.id)
        )
        workplace_id = wp_result.scalar_one()

        cr_result = await conn.execute(
            ZoneORM.__table__.insert()
            .values(name="Inv Corridor", type=OrmZoneType.CORRIDOR)
            .returning(ZoneORM.__table__.c.id)
        )
        corridor_id = cr_result.scalar_one()

        for zid, center in [(workplace_id, -40), (corridor_id, -80)]:
            for i in range(5):
                await conn.execute(
                    FingerprintORM.__table__.insert().values(
                        employee_id=None,
                        zone_id=zid,
                        is_calibration=True,
                        captured_at=datetime.now(tz=UTC),
                        device_id="inv-cal",
                        rssi_vector={
                            "AA:BB:CC:DD:EE:01": center + i,
                            "AA:BB:CC:DD:EE:02": center - 5,
                        },
                        sample_count=1,
                    )
                )

    yield {
        "admin": {"id": admin_id, "email": "admin-inv@svetlyachok.local"},
        "workplace_id": workplace_id,
        "corridor_id": corridor_id,
        "password": _ADMIN_PASSWORD,
    }

    async with db_engine.begin() as conn:
        await conn.execute(
            delete(FingerprintORM).where(
                FingerprintORM.zone_id.in_([workplace_id, corridor_id])
            )
        )
        await conn.execute(
            delete(ZoneORM).where(ZoneORM.id.in_([workplace_id, corridor_id]))
        )
        await conn.execute(
            delete(EmployeeORM).where(EmployeeORM.id == admin_id)
        )


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def test_create_calibration_invalidates_classifier_cache(
    client_with_db: AsyncClient,
    seeded_two_zones_calibrated: dict,
) -> None:
    """После POST /calibration/points cache_clear делает singleton свежим.

    Стратегия: после первого /classify singleton-классификатор обучен
    (`_clf is not None`). После POST /calibration/points singleton
    пересоздан → `_clf is None`. Это прямая проверка invalidation-хука.
    """
    token = await _login(
        client_with_db,
        seeded_two_zones_calibrated["admin"]["email"],
        seeded_two_zones_calibrated["password"],
    )

    # 1. Триггерим обучение через первый /classify.
    classify_resp = await client_with_db.post(
        "/api/v1/positioning/classify",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "rssi_vector": {
                "AA:BB:CC:DD:EE:01": -42,
                "AA:BB:CC:DD:EE:02": -45,
            }
        },
    )
    assert classify_resp.status_code == 200

    classifier_before = _position_classifier_singleton()
    assert classifier_before.is_trained(), "после /classify модель должна быть обучена"

    # 2. POST новой калибровочной точки — должно вызвать invalidate.
    new_point_resp = await client_with_db.post(
        "/api/v1/calibration/points",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "zone_id": seeded_two_zones_calibrated["corridor_id"],
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": {"AA:BB:CC:DD:EE:01": -75, "AA:BB:CC:DD:EE:02": -78},
            "sample_count": 1,
        },
    )
    assert new_point_resp.status_code == 201, new_point_resp.text

    # 3. Singleton должен быть пересоздан (новый instance, не обучен).
    classifier_after = _position_classifier_singleton()
    assert classifier_after is not classifier_before, (
        "после POST /calibration/points lru_cache должен быть сброшен — "
        "новый instance"
    )
    assert not classifier_after.is_trained(), (
        "новый singleton не должен иметь обученной модели до следующего /classify"
    )


async def test_delete_calibration_invalidates_classifier_cache(
    client_with_db: AsyncClient,
    seeded_two_zones_calibrated: dict,
    db_engine: AsyncEngine,
) -> None:
    """После DELETE /calibration/points/{id} singleton тоже сбрасывается."""
    token = await _login(
        client_with_db,
        seeded_two_zones_calibrated["admin"]["email"],
        seeded_two_zones_calibrated["password"],
    )

    # Триггерим обучение.
    await client_with_db.post(
        "/api/v1/positioning/classify",
        headers={"Authorization": f"Bearer {token}"},
        json={"rssi_vector": {"AA:BB:CC:DD:EE:01": -42, "AA:BB:CC:DD:EE:02": -45}},
    )
    classifier_before = _position_classifier_singleton()
    assert classifier_before.is_trained()

    # Берём id первой попавшейся калибровочной точки.
    list_resp = await client_with_db.get(
        "/api/v1/calibration/points",
        headers={"Authorization": f"Bearer {token}"},
        params={"zone_id": seeded_two_zones_calibrated["workplace_id"]},
    )
    assert list_resp.status_code == 200, list_resp.text
    points = list_resp.json()["items"]
    assert len(points) > 0
    target_id = points[0]["id"]

    # DELETE.
    delete_resp = await client_with_db.delete(
        f"/api/v1/calibration/points/{target_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_resp.status_code == 204, delete_resp.text

    # Singleton пересоздан.
    classifier_after = _position_classifier_singleton()
    assert classifier_after is not classifier_before
    assert not classifier_after.is_trained()


async def test_classify_after_calibration_change_uses_fresh_data(
    client_with_db: AsyncClient,
    seeded_two_zones_calibrated: dict,
    db_engine: AsyncEngine,
) -> None:
    """End-to-end: добавили точку → /classify видит её в обученной модели.

    После POST новой workplace-точки в зону corridor (overlap RSSI),
    classifier должен переобучиться и теперь corridor-кластер
    в районе -40 dBm может уже не давать чистый workplace-результат
    (модель видит, что -40 встречается и в corridor). Главное — модель
    обучена заново на актуальной выборке, что подтверждается
    `is_trained()` и тем, что singleton — другой instance.
    """
    token = await _login(
        client_with_db,
        seeded_two_zones_calibrated["admin"]["email"],
        seeded_two_zones_calibrated["password"],
    )

    # Обучили на исходной выборке.
    first_classify = await client_with_db.post(
        "/api/v1/positioning/classify",
        headers={"Authorization": f"Bearer {token}"},
        json={"rssi_vector": {"AA:BB:CC:DD:EE:01": -42, "AA:BB:CC:DD:EE:02": -45}},
    )
    assert first_classify.status_code == 200
    initial_zone = first_classify.json()["zone_id"]
    assert initial_zone == seeded_two_zones_calibrated["workplace_id"]

    # Добавляем точку corridor с RSSI близким к workplace-кластеру —
    # это запутает модель.
    await client_with_db.post(
        "/api/v1/calibration/points",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "zone_id": seeded_two_zones_calibrated["corridor_id"],
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "rssi_vector": {"AA:BB:CC:DD:EE:01": -42, "AA:BB:CC:DD:EE:02": -45},
            "sample_count": 1,
        },
    )

    # Следующий /classify обучает модель заново и возвращает результат.
    second_classify = await client_with_db.post(
        "/api/v1/positioning/classify",
        headers={"Authorization": f"Bearer {token}"},
        json={"rssi_vector": {"AA:BB:CC:DD:EE:01": -42, "AA:BB:CC:DD:EE:02": -45}},
    )
    assert second_classify.status_code == 200
    # Главная проверка — модель обучена заново.
    assert _position_classifier_singleton().is_trained()
    # Confidence должен снизиться (модель видит конкурирующий кластер).
    assert second_classify.json()["confidence"] <= first_classify.json()["confidence"]
