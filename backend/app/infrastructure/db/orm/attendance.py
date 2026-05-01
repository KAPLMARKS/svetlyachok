"""ORM-модель записи учёта посещаемости.

Каждая запись соответствует одной «сессии» нахождения сотрудника в зоне:
от пересечения границы зоны до выхода из неё. Открытая сессия
(сотрудник ещё в зоне) имеет `ended_at IS NULL`.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, BigIntPK, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.db.orm.employees import Employee
    from app.infrastructure.db.orm.zones import Zone


class AttendanceStatus(str, enum.Enum):
    """Статус сессии присутствия после пост-обработки.

    Вычисляется правилами: сравнение `started_at` с `Employee.schedule_start`,
    учёт интервалов между сменами и т. д. Алгоритм будет реализован на
    вехе «Учёт рабочего времени».
    """

    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"
    OVERTIME = "overtime"


class AttendanceLog(Base, TimestampMixin):
    """Запись о пребывании сотрудника в зоне."""

    __tablename__ = "attendance_logs"

    id: Mapped[BigIntPK]

    # При удалении сотрудника удаляем все его логи — это PII и хранить
    # их без владельца нет смысла.
    employee_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # RESTRICT: нельзя удалить зону, на которую есть исторические логи.
    # Для архивации зон — soft-delete (добавим столбец `archived_at` если
    # потребуется), а не физическое удаление.
    zone_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("zones.id", ondelete="RESTRICT"),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    # NULL = открытая сессия. Закроется, когда сотрудник перейдёт в другую
    # зону или завершится рабочий день.
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Денормализованная длительность для быстрых отчётов. Заполняется
    # при закрытии сессии. Хранение отдельным полем + CHECK выгоднее
    # вычисляемого столбца на больших отчётах.
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[AttendanceStatus] = mapped_column(
        SqlEnum(
            AttendanceStatus,
            name="attendance_status_enum",
            native_enum=True,
            create_type=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'present'"),
    )

    employee: Mapped[Employee] = relationship(
        back_populates="attendance_logs",
    )
    zone: Mapped[Zone] = relationship(
        back_populates="attendance_logs",
    )

    __table_args__ = (
        # Сессия не может закончиться раньше, чем началась.
        CheckConstraint(
            "ended_at IS NULL OR ended_at > started_at",
            name="ended_after_started",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="duration_non_negative",
        ),
        # Главный индекс отчётов: «логи сотрудника за период».
        Index(
            "ix_attendance_logs_employee_started",
            "employee_id",
            "started_at",
        ),
        Index("ix_attendance_logs_zone", "zone_id"),
        # Partial-index для быстрого ответа на «кто сейчас на работе».
        # Записей с ended_at IS NULL мало (≤ численности персонала),
        # отдельный индекс заметно ускоряет такие выборки.
        Index(
            "ix_attendance_logs_open_sessions",
            "employee_id",
            postgresql_where=text("ended_at IS NULL"),
        ),
    )
