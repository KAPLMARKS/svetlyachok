"""ORM-модель радиоотпечатка (RSSI fingerprint).

Fingerprint бывает двух видов:

1. **Калибровочный** (`is_calibration=True`): эталонная точка, привязанная
   к зоне через `zone_id`. Используется как обучающая выборка для WKNN
   и Random Forest.
2. **Live** (`is_calibration=False`): отпечаток, прилетевший от устройства
   сотрудника во время работы. Может ещё не иметь `zone_id` — назначится
   после классификации.

`rssi_vector` — JSONB вида `{"AA:BB:CC:DD:EE:01": -45, ...}` (BSSID → dBm).
JSONB позволяет хранить переменное число точек доступа без отдельной
таблицы и индексировать по содержимому при необходимости.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, BigIntPK, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.db.orm.employees import Employee
    from app.infrastructure.db.orm.zones import Zone


class Fingerprint(Base, TimestampMixin):
    """Радиоотпечаток (RSSI vector в фиксированный момент времени)."""

    __tablename__ = "fingerprints"

    id: Mapped[BigIntPK]

    # Сотрудник, чьё устройство сделало замер. Nullable — у калибровочных
    # отпечатков может не быть конкретного «автора», их закладывает админ.
    # ondelete=SET NULL: при удалении сотрудника отпечатки сохраняются для
    # дальнейшего обучения моделей (PII-данных в RSSI-векторе нет).
    employee_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Зона, к которой относится отпечаток. Для live-замеров ставится после
    # классификации; для калибровочных — обязательно (см. CHECK ниже).
    zone_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("zones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_calibration: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Идентификатор устройства Android (для отладки и привязки серий
    # измерений к одному телефону). Может быть пустым для отпечатков,
    # импортированных из других источников.
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Сам RSSI-вектор: BSSID -> dBm (всегда отрицательное число).
    # JSONB используем намеренно: количество видимых AP меняется от
    # сканирования к сканированию, нормализация в отдельную таблицу
    # сильно увеличит число записей и усложнит выборку для ML.
    rssi_vector: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Сколько отдельных сканов агрегировано в этот отпечаток. На устройстве
    # обычно делается серия сканов и усредняется RSSI — это значение
    # позволяет ML-сервисам учитывать «вес» наблюдения.
    sample_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )

    employee: Mapped[Employee | None] = relationship(
        foreign_keys=[employee_id],
    )
    zone: Mapped[Zone | None] = relationship(
        back_populates="fingerprints",
        foreign_keys=[zone_id],
    )

    __table_args__ = (
        CheckConstraint("sample_count > 0", name="sample_count_positive"),
        # Доменный инвариант: калибровочный отпечаток обязан быть привязан
        # к зоне. Иначе он бесполезен для обучения ML.
        CheckConstraint(
            "(is_calibration = false) OR (zone_id IS NOT NULL)",
            name="calibration_requires_zone",
        ),
        # Композитный индекс: «последние отпечатки сотрудника» —
        # типовой запрос для построения дашборда или подсчёта присутствия.
        Index(
            "ix_fingerprints_employee_captured",
            "employee_id",
            "captured_at",
        ),
        # Композитный индекс: построение калибровочного набора по зоне.
        Index(
            "ix_fingerprints_zone_calibration",
            "zone_id",
            "is_calibration",
        ),
    )
