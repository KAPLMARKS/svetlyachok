"""Seed-скрипт для dev-окружения.

Заполняет БД минимальным набором данных для ручного тестирования API
и веб-панели:

- 5 зон (4 типа: рабочее место, коридор, переговорная, вне офиса)
- 2 учётных записи (admin + employee)
- 3 калибровочных fingerprint'а (по одному на разные зоны)

Скрипт идемпотентен: использует `INSERT ... ON CONFLICT DO NOTHING`
по уникальным колонкам (`zones.name`, `employees.email`). Повторный
запуск ничего не сломает; будет только увеличиваться счётчик skipped.

Запуск:
    cd backend && python scripts/seed.py

Перед запуском должен быть применён `alembic upgrade head`.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, time
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.db.orm import (
    Employee,
    Fingerprint,
    Role,
    Zone,
    ZoneType,
)
from app.infrastructure.db.session import (
    dispose_engine,
    get_sessionmaker,
    init_engine,
)

log = get_logger(__name__)


# ----------------------------------------------------------------------------
# Тестовые данные
# ----------------------------------------------------------------------------

ZONES_SEED: list[dict] = [
    {
        "name": "Рабочее место А1",
        "type": ZoneType.WORKPLACE,
        "description": "Тестовое рабочее место №1.",
        "display_color": "#4A90E2",
    },
    {
        "name": "Рабочее место Б3",
        "type": ZoneType.WORKPLACE,
        "description": "Тестовое рабочее место №2.",
        "display_color": "#4A90E2",
    },
    {
        "name": "Коридор южный",
        "type": ZoneType.CORRIDOR,
        "description": "Транзитный коридор между секциями офиса.",
        "display_color": "#9B9B9B",
    },
    {
        "name": "Переговорная Малая",
        "type": ZoneType.MEETING_ROOM,
        "description": "Переговорная комната до 4 человек.",
        "display_color": "#F5A623",
    },
    {
        "name": "Вне офиса",
        "type": ZoneType.OUTSIDE_OFFICE,
        "description": "Маркер для случая, когда сотрудник не определён ни в одной офисной зоне.",
        "display_color": "#D0021B",
    },
]


# Hashed_password — заглушка. Реальный bcrypt-хеш появится на вехе
# «Аутентификация (JWT)»; тогда же будет и /api/v1/auth/register.
_PLACEHOLDER_PASSWORD = "PLACEHOLDER_seed_only_replace_on_auth_milestone"  # noqa: S105

EMPLOYEES_SEED: list[dict] = [
    {
        "email": "admin@svetlyachok.local",
        "full_name": "Админ Тестовый",
        "role": Role.ADMIN,
        "hashed_password": _PLACEHOLDER_PASSWORD,
        "is_active": True,
        "schedule_start": None,
        "schedule_end": None,
    },
    {
        "email": "employee@svetlyachok.local",
        "full_name": "Иванов Иван Иванович",
        "role": Role.EMPLOYEE,
        "hashed_password": _PLACEHOLDER_PASSWORD,
        "is_active": True,
        "schedule_start": time(9, 0),
        "schedule_end": time(18, 0),
    },
]


# Калибровочные отпечатки: по одному на 3 разных типа зон. RSSI-значения
# выдуманные, но реалистичные (в офисах обычно -40..-90 dBm).
CALIBRATION_FINGERPRINTS_SEED: list[dict] = [
    {
        "zone_name": "Рабочее место А1",
        "rssi_vector": {
            "AA:BB:CC:DD:EE:01": -45,
            "AA:BB:CC:DD:EE:02": -67,
            "AA:BB:CC:DD:EE:03": -82,
        },
        "device_id": "seed-device",
        "sample_count": 5,
    },
    {
        "zone_name": "Коридор южный",
        "rssi_vector": {
            "AA:BB:CC:DD:EE:01": -72,
            "AA:BB:CC:DD:EE:02": -55,
            "AA:BB:CC:DD:EE:03": -78,
        },
        "device_id": "seed-device",
        "sample_count": 5,
    },
    {
        "zone_name": "Переговорная Малая",
        "rssi_vector": {
            "AA:BB:CC:DD:EE:01": -88,
            "AA:BB:CC:DD:EE:02": -70,
            "AA:BB:CC:DD:EE:03": -50,
        },
        "device_id": "seed-device",
        "sample_count": 5,
    },
]


async def _seed_zones() -> tuple[int, int]:
    """Возвращает (inserted, skipped)."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        stmt = (
            pg_insert(Zone.__table__)
            .values(ZONES_SEED)
            .on_conflict_do_nothing(index_elements=["name"])
            .returning(Zone.__table__.c.id)
        )
        result = await session.execute(stmt)
        inserted = len(result.scalars().all())
    skipped = len(ZONES_SEED) - inserted
    log.info("[seed.zones] done", inserted=inserted, skipped=skipped)
    return inserted, skipped


async def _seed_employees() -> tuple[int, int]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        stmt = (
            pg_insert(Employee.__table__)
            .values(EMPLOYEES_SEED)
            .on_conflict_do_nothing(index_elements=["email"])
            .returning(Employee.__table__.c.id)
        )
        result = await session.execute(stmt)
        inserted = len(result.scalars().all())
    skipped = len(EMPLOYEES_SEED) - inserted
    log.info("[seed.employees] done", inserted=inserted, skipped=skipped)
    return inserted, skipped


async def _seed_fingerprints() -> tuple[int, int]:
    """Идемпотентность по фингерпринтам: проверяем, что калибровочный
    отпечаток для зоны уже есть, и пропускаем при наличии.

    На fingerprints нет натурального unique-ключа (несколько калибровок
    одной зоны — норма для накопления выборки), поэтому ON CONFLICT
    не подходит. Используем явный pre-check: если хоть один калибровочный
    отпечаток уже есть для этой зоны от seed-устройства — пропускаем.
    """
    sessionmaker = get_sessionmaker()
    inserted = 0
    skipped = 0
    now = datetime.now(tz=UTC)

    async with sessionmaker() as session:
        for entry in CALIBRATION_FINGERPRINTS_SEED:
            zone_id_stmt = select(Zone.id).where(Zone.name == entry["zone_name"])
            zone_id = (await session.execute(zone_id_stmt)).scalar_one_or_none()
            if zone_id is None:
                log.warning(
                    "[seed.fingerprints] zone missing, skip",
                    zone_name=entry["zone_name"],
                )
                skipped += 1
                continue

            exists_stmt = select(Fingerprint.id).where(
                Fingerprint.zone_id == zone_id,
                Fingerprint.is_calibration.is_(True),
                Fingerprint.device_id == entry["device_id"],
            )
            already = (await session.execute(exists_stmt)).first()
            if already is not None:
                skipped += 1
                continue

            session.add(
                Fingerprint(
                    employee_id=None,
                    zone_id=zone_id,
                    is_calibration=True,
                    captured_at=now,
                    device_id=entry["device_id"],
                    rssi_vector=entry["rssi_vector"],
                    sample_count=entry["sample_count"],
                )
            )
            inserted += 1

        await session.commit()

    log.info("[seed.fingerprints] done", inserted=inserted, skipped=skipped)
    return inserted, skipped


async def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    db_host = urlparse(settings.database_url.unicode_string()).hostname or "unknown"
    log.info(
        "[seed] start",
        environment=settings.environment,
        database_host=db_host,
    )

    init_engine(settings)

    try:
        zones_ins, zones_skip = await _seed_zones()
        emp_ins, emp_skip = await _seed_employees()
        fp_ins, fp_skip = await _seed_fingerprints()
    except Exception:
        log.error("[seed] failed", exc_info=True)
        await dispose_engine()
        return 1

    await dispose_engine()

    log.info(
        "[seed] complete",
        zones=f"{zones_ins} inserted / {zones_skip} skipped",
        employees=f"{emp_ins} inserted / {emp_skip} skipped",
        fingerprints=f"{fp_ins} inserted / {fp_skip} skipped",
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
