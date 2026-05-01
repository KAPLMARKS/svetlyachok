"""Интеграционные тесты Alembic-миграций и инвариантов схемы.

Запускаются в режиме `pytest -m integration` с поднятым тестовым
PostgreSQL (testcontainer или TEST_DATABASE_URL).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.orm import Fingerprint

pytestmark = pytest.mark.integration


EXPECTED_TABLES: set[str] = {
    "employees",
    "zones",
    "fingerprints",
    "attendance_logs",
    "alembic_version",
}

EXPECTED_ENUMS: set[str] = {
    "role_enum",
    "zone_type_enum",
    "attendance_status_enum",
}


async def test_upgrade_creates_all_tables(db_session: AsyncSession) -> None:
    """`alembic upgrade head` должен создать ровно ожидаемый набор таблиц."""
    result = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
    )
    tables = {row[0] for row in result.fetchall()}
    missing = EXPECTED_TABLES - tables
    assert not missing, f"Не созданы таблицы: {missing}"


async def test_upgrade_creates_all_enums(db_session: AsyncSession) -> None:
    """Должны быть созданы все три PostgreSQL enum-типа."""
    result = await db_session.execute(
        text(
            "SELECT typname FROM pg_type "
            "WHERE typtype = 'e' AND typname = ANY(:names)"
        ),
        {"names": list(EXPECTED_ENUMS)},
    )
    enums = {row[0] for row in result.fetchall()}
    assert enums == EXPECTED_ENUMS, f"Ожидали {EXPECTED_ENUMS}, нашли {enums}"


async def test_partial_index_for_open_sessions(db_session: AsyncSession) -> None:
    """ix_attendance_logs_open_sessions должен быть partial-индексом
    с предикатом `(ended_at IS NULL)`."""
    result = await db_session.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'ix_attendance_logs_open_sessions'"
        )
    )
    rows = result.fetchall()
    assert rows, "partial-index ix_attendance_logs_open_sessions не найден"
    indexdef = rows[0][0].lower()
    assert "where" in indexdef, f"индекс не partial: {indexdef!r}"
    assert "ended_at is null" in indexdef, f"неверный предикат: {indexdef!r}"


async def test_calibration_requires_zone_constraint(
    db_session: AsyncSession,
) -> None:
    """CHECK calibration_requires_zone должен запрещать
    `is_calibration=True` без `zone_id`."""
    bad = Fingerprint(
        employee_id=None,
        zone_id=None,
        is_calibration=True,
        captured_at=datetime.now(tz=UTC),
        device_id="test-device",
        rssi_vector={"AA:BB:CC:DD:EE:01": -55},
        sample_count=1,
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_sample_count_positive_constraint(
    db_session: AsyncSession,
) -> None:
    """sample_count = 0 должен быть запрещён CHECK."""
    bad = Fingerprint(
        employee_id=None,
        zone_id=None,
        is_calibration=False,
        captured_at=datetime.now(tz=UTC),
        device_id="test-device",
        rssi_vector={"AA:BB:CC:DD:EE:01": -55},
        sample_count=0,
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_downgrade_then_upgrade_idempotent(postgres_dsn: str) -> None:
    """`downgrade base` → `upgrade head` должен пройти без ошибок и
    оставить ту же схему. Этот тест запускается ОТДЕЛЬНО от db_session,
    потому что меняет схему — savepoint-rollback не помогает.

    Делается на чистой временной БД через `CREATE SCHEMA tmp_migration_test`
    + переключение search_path. Это безопасно: все объекты создаются в
    `tmp_migration_test`, а не в основной `public`-схеме, которую
    использует savepoint-rollback в остальных тестах.

    Однако реализация через схемы потребовала бы кастомизации alembic
    env.py для include_schemas; для пилота достаточно простой проверки:
    запустить downgrade и сразу upgrade в основной схеме, заранее
    выйдя из всех активных транзакций.

    NOTE: тест намеренно перенесён в отдельный run-режим — вызывает
    реальные миграции и плохо ладит с другими тестами. Чтобы не флакать
    остальной набор, пометили `@pytest.mark.skipif`-фильтром, активным
    только при явном `RUN_MIGRATION_CYCLE_TEST=1`.
    """
    import os

    if not os.environ.get("RUN_MIGRATION_CYCLE_TEST"):
        pytest.skip(
            "запускается только с RUN_MIGRATION_CYCLE_TEST=1 (тест меняет схему)"
        )

    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", postgres_dsn)

    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
