"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-01 16:10:00.000000

Создаёт первичную схему БД проекта АИС «Светлячок»:

- 3 enum-типа: role_enum, zone_type_enum, attendance_status_enum
- 4 таблицы: employees, zones, fingerprints, attendance_logs
- Все индексы (включая partial для открытых сессий учёта посещаемости)
- Все CHECK constraints (инвариант калибровочного отпечатка, валидация
  HEX-цвета зоны, корректность длительности сессии и т. д.)

Миграция написана вручную, а не через autogenerate, потому что:
1. Среда разработки на момент создания не имела свежего Postgres,
   на котором можно было бы запустить autogenerate.
2. Initial-схема структурно простая — ручная версия читаемее и не
   содержит мусора от autogenerate (лишние alter'ы, переименования).
3. Partial-index `ix_attendance_logs_open_sessions` autogenerate
   часто упускает; ручная миграция гарантированно ставит `WHERE`-условие.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum types — должны быть созданы до таблиц, которые на них ссылаются.
    # ------------------------------------------------------------------
    role_enum = postgresql.ENUM(
        "admin",
        "employee",
        name="role_enum",
        create_type=False,
    )
    role_enum.create(op.get_bind(), checkfirst=True)

    zone_type_enum = postgresql.ENUM(
        "workplace",
        "corridor",
        "meeting_room",
        "outside_office",
        name="zone_type_enum",
        create_type=False,
    )
    zone_type_enum.create(op.get_bind(), checkfirst=True)

    attendance_status_enum = postgresql.ENUM(
        "present",
        "late",
        "absent",
        "overtime",
        name="attendance_status_enum",
        create_type=False,
    )
    attendance_status_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # employees
    # ------------------------------------------------------------------
    op.create_table(
        "employees",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "admin",
                "employee",
                name="role_enum",
                create_type=False,
            ),
            server_default=sa.text("'employee'"),
            nullable=False,
        ),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("schedule_start", sa.Time(timezone=False), nullable=True),
        sa.Column("schedule_end", sa.Time(timezone=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "schedule_start IS NULL "
            "OR schedule_end IS NULL "
            "OR schedule_start < schedule_end",
            name="schedule_order",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_employees"),
        sa.UniqueConstraint("email", name="uq_employees_email"),
    )
    op.create_index("ix_employees_email", "employees", ["email"], unique=False)
    op.create_index(
        "ix_employees_role_active",
        "employees",
        ["role", "is_active"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # zones
    # ------------------------------------------------------------------
    op.create_table(
        "zones",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "workplace",
                "corridor",
                "meeting_room",
                "outside_office",
                name="zone_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("display_color", sa.String(length=7), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "display_color IS NULL OR display_color ~ '^#[0-9A-Fa-f]{6}$'",
            name="display_color_hex",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_zones"),
        sa.UniqueConstraint("name", name="uq_zones_name"),
    )
    op.create_index("ix_zones_type", "zones", ["type"], unique=False)

    # ------------------------------------------------------------------
    # fingerprints
    # ------------------------------------------------------------------
    op.create_table(
        "fingerprints",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("employee_id", sa.BigInteger(), nullable=True),
        sa.Column("zone_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "is_calibration",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=True),
        sa.Column("rssi_vector", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "sample_count",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(is_calibration = false) OR (zone_id IS NOT NULL)",
            name="calibration_requires_zone",
        ),
        sa.CheckConstraint("sample_count > 0", name="sample_count_positive"),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_fingerprints_employee_id_employees",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["zones.id"],
            name="fk_fingerprints_zone_id_zones",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fingerprints"),
    )
    op.create_index(
        "ix_fingerprints_employee_id",
        "fingerprints",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_fingerprints_zone_id",
        "fingerprints",
        ["zone_id"],
        unique=False,
    )
    op.create_index(
        "ix_fingerprints_employee_captured",
        "fingerprints",
        ["employee_id", "captured_at"],
        unique=False,
    )
    op.create_index(
        "ix_fingerprints_zone_calibration",
        "fingerprints",
        ["zone_id", "is_calibration"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # attendance_logs
    # ------------------------------------------------------------------
    op.create_table(
        "attendance_logs",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("zone_id", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "present",
                "late",
                "absent",
                "overtime",
                name="attendance_status_enum",
                create_type=False,
            ),
            server_default=sa.text("'present'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="duration_non_negative",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at > started_at",
            name="ended_after_started",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_attendance_logs_employee_id_employees",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["zones.id"],
            name="fk_attendance_logs_zone_id_zones",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_attendance_logs"),
    )
    op.create_index(
        "ix_attendance_logs_employee_id",
        "attendance_logs",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_attendance_logs_employee_started",
        "attendance_logs",
        ["employee_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_attendance_logs_zone",
        "attendance_logs",
        ["zone_id"],
        unique=False,
    )
    # Partial index: только открытые сессии (ended_at IS NULL).
    # Очень эффективен для ответа на вопрос «кто сейчас на работе».
    op.create_index(
        "ix_attendance_logs_open_sessions",
        "attendance_logs",
        ["employee_id"],
        unique=False,
        postgresql_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    # Удаляем в обратном порядке: сначала таблицы (с их индексами/FK),
    # затем enum-типы.

    op.drop_index("ix_attendance_logs_open_sessions", table_name="attendance_logs")
    op.drop_index("ix_attendance_logs_zone", table_name="attendance_logs")
    op.drop_index("ix_attendance_logs_employee_started", table_name="attendance_logs")
    op.drop_index("ix_attendance_logs_employee_id", table_name="attendance_logs")
    op.drop_table("attendance_logs")

    op.drop_index("ix_fingerprints_zone_calibration", table_name="fingerprints")
    op.drop_index("ix_fingerprints_employee_captured", table_name="fingerprints")
    op.drop_index("ix_fingerprints_zone_id", table_name="fingerprints")
    op.drop_index("ix_fingerprints_employee_id", table_name="fingerprints")
    op.drop_table("fingerprints")

    op.drop_index("ix_zones_type", table_name="zones")
    op.drop_table("zones")

    op.drop_index("ix_employees_role_active", table_name="employees")
    op.drop_index("ix_employees_email", table_name="employees")
    op.drop_table("employees")

    sa.Enum(name="attendance_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="zone_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="role_enum").drop(op.get_bind(), checkfirst=True)
