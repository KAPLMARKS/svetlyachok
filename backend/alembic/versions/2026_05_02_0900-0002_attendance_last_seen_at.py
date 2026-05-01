"""add last_seen_at column to attendance_logs

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-02 09:00:00.000000

Добавляет столбец `last_seen_at` (timestamptz NOT NULL) в attendance_logs.

Зачем нужен:

Use case `RecordAttendanceUseCase` использует это поле для inactivity-
timeout: при каждом классификации в той же зоне `last_seen_at`
обновляется на текущее время. Если разница `now - last_seen_at`
превышает порог (`ATTENDANCE_INACTIVITY_TIMEOUT_SECONDS`, по умолчанию
30 минут), сессия закрывается с `ended_at = last_seen_at`, и открывается
новая. Это позволяет корректно учитывать перерывы и уход домой.

Стратегия миграции:

1. Добавляем столбец с server_default=now() — для совместимости с
   существующими записями (если такие есть на dev/тестовых БД).
2. Сразу убираем default через ALTER COLUMN ... DROP DEFAULT —
   приложение всегда передаёт значение явно из use case, а не полагается
   на server-side default.

NOT NULL — потому что для каждой записи (даже закрытой ранее) корректное
значение известно: оно либо равно `started_at` (если запись никогда не
расширялась), либо реальному моменту последнего апдейта. На свежей БД
это будет server-default = now().
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Добавляем колонку с server_default для backfill существующих строк.
    op.add_column(
        "attendance_logs",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Убираем server_default — значение всегда задаётся приложением.
    op.alter_column("attendance_logs", "last_seen_at", server_default=None)


def downgrade() -> None:
    op.drop_column("attendance_logs", "last_seen_at")
