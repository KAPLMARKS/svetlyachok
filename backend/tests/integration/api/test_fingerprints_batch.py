"""Интеграционные тесты POST /api/v1/fingerprints/batch.

Проверяют partial-success-семантику и Pydantic-validation guard на
размере batch'а. Авторизация прозрачно использует тот же
`get_current_user`, что и одиночный submit, поэтому отдельный
unauthorized-тест не дублируем (есть в test_fingerprints.py).
"""

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

_EMPLOYEE_PASSWORD = "employee-batch-12345"


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    limiter.reset()


@pytest.fixture
async def seeded_employee(
    db_engine: AsyncEngine,
) -> AsyncIterator[dict[str, str | int]]:
    hasher = BcryptPasswordHasher()
    async with db_engine.begin() as conn:
        emp_result = await conn.execute(
            EmployeeORM.__table__.insert()
            .values(
                email="emp-batch@svetlyachok.local",
                full_name="Emp Batch",
                role=Role.EMPLOYEE,
                hashed_password=hasher.hash(_EMPLOYEE_PASSWORD),
                is_active=True,
            )
            .returning(EmployeeORM.__table__.c.id)
        )
        emp_id = emp_result.scalar_one()

    yield {
        "id": emp_id,
        "email": "emp-batch@svetlyachok.local",
        "password": _EMPLOYEE_PASSWORD,
    }

    async with db_engine.begin() as conn:
        await conn.execute(
            delete(FingerprintORM).where(FingerprintORM.employee_id == emp_id)
        )
        await conn.execute(delete(EmployeeORM).where(EmployeeORM.id == emp_id))


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _vector() -> dict[str, int]:
    return {"AA:BB:CC:DD:EE:01": -50, "AA:BB:CC:DD:EE:02": -68}


def _item(captured_at: datetime) -> dict:
    return {
        "captured_at": captured_at.isoformat(),
        "rssi_vector": _vector(),
        "sample_count": 1,
        "device_id": "batch-dev",
    }


async def test_batch_all_accepted(
    client_with_db: AsyncClient,
    seeded_employee: dict[str, str | int],
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_employee["email"]),
        str(seeded_employee["password"]),
    )
    now = datetime.now(tz=UTC)

    response = await client_with_db.post(
        "/api/v1/fingerprints/batch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "items": [
                _item(now),
                _item(now - timedelta(seconds=10)),
                _item(now - timedelta(seconds=20)),
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_count"] == 3
    assert body["rejected_count"] == 0
    assert body["rejected"] == []
    assert [a["index"] for a in body["accepted"]] == [0, 1, 2]
    for a in body["accepted"]:
        assert a["fingerprint"]["employee_id"] == seeded_employee["id"]
        assert a["fingerprint"]["is_calibration"] is False


async def test_batch_partial_success(
    client_with_db: AsyncClient,
    seeded_employee: dict[str, str | int],
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_employee["email"]),
        str(seeded_employee["password"]),
    )
    now = datetime.now(tz=UTC)

    response = await client_with_db.post(
        "/api/v1/fingerprints/batch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "items": [
                _item(now),
                _item(now + timedelta(hours=2)),  # rejected
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 1
    assert [a["index"] for a in body["accepted"]] == [0]
    assert body["rejected"][0]["index"] == 1
    assert body["rejected"][0]["code"] == "captured_at_in_future"


async def test_batch_too_many_items_rejected_by_pydantic(
    client_with_db: AsyncClient,
    seeded_employee: dict[str, str | int],
) -> None:
    token = await _login(
        client_with_db,
        str(seeded_employee["email"]),
        str(seeded_employee["password"]),
    )
    now = datetime.now(tz=UTC)

    response = await client_with_db.post(
        "/api/v1/fingerprints/batch",
        headers={"Authorization": f"Bearer {token}"},
        json={"items": [_item(now)] * 101},
    )

    # Pydantic max_length=100 — FastAPI отдаёт 422.
    assert response.status_code == 422, response.text
