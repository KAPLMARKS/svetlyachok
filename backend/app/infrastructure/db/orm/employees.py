"""ORM-модель сотрудника + enum роли.

Эта модель — частная реализация infrastructure-слоя. Domain работает
с собственными dataclass'ами (см. `app/domain/employees/`); конвертация
domain ↔ ORM выполняется в репозитории на вехе CRUD.

Хеширование пароля будет добавлено на вехе «Аутентификация» — пока
поле `hashed_password` хранит литерал и валидируется только на длину.
"""

from __future__ import annotations

import enum
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Index, String, Time, text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, BigIntPK, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.db.orm.attendance import AttendanceLog


class Role(str, enum.Enum):
    """Роль сотрудника в системе.

    - ADMIN — администратор: настраивает зоны, калибрует радиокарту,
      управляет пользователями
    - EMPLOYEE — рядовой сотрудник: только сканирует Wi-Fi и просматривает
      собственный учёт времени
    """

    ADMIN = "admin"
    EMPLOYEE = "employee"


class Employee(Base, TimestampMixin):
    """Сотрудник (учётная запись пользователя)."""

    __tablename__ = "employees"

    id: Mapped[BigIntPK]

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        SqlEnum(
            Role,
            name="role_enum",
            native_enum=True,
            create_type=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'employee'"),
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    # Плановое расписание (опционально). Если задано — сравнивается со
    # временем входа в зону для расчёта опозданий/переработок.
    schedule_start: Mapped[time | None] = mapped_column(Time(timezone=False), nullable=True)
    schedule_end: Mapped[time | None] = mapped_column(Time(timezone=False), nullable=True)

    # Реальная связь объявляется в attendance.py через back_populates.
    attendance_logs: Mapped[list[AttendanceLog]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # Партий быстрого поиска активных сотрудников по роли (списки
        # «все админы», «все активные сотрудники»).
        Index("ix_employees_role_active", "role", "is_active"),
        # Если расписание задано — start должен быть строго раньше end.
        # Случай "ночной смены" (start > end) сейчас не поддерживается;
        # появится — добавим отдельный флаг и миграцию.
        CheckConstraint(
            "schedule_start IS NULL "
            "OR schedule_end IS NULL "
            "OR schedule_start < schedule_end",
            name="schedule_order",
        ),
    )
