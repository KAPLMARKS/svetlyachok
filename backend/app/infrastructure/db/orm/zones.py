"""ORM-модель зоны (помещения / классификационной области) + enum типа.

Зона — это область, которую система должна определять по радиоотпечатку.
Тип задан жёстко набором, согласованным в `.ai-factory/DESCRIPTION.md`:
рабочее место, коридор, переговорная, вне офиса.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base, BigIntPK, TimestampMixin

if TYPE_CHECKING:
    from app.infrastructure.db.orm.attendance import AttendanceLog
    from app.infrastructure.db.orm.radiomap import Fingerprint


class ZoneType(str, enum.Enum):
    """Тип зоны для классификации позиции.

    Совпадает с метриками в ISO/IEC 18305:2016 — Detection Probability
    считается отдельно по каждому типу.
    """

    WORKPLACE = "workplace"
    CORRIDOR = "corridor"
    MEETING_ROOM = "meeting_room"
    OUTSIDE_OFFICE = "outside_office"


class Zone(Base, TimestampMixin):
    """Зона учёта посещаемости (помещение/область)."""

    __tablename__ = "zones"

    id: Mapped[BigIntPK]

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    type: Mapped[ZoneType] = mapped_column(
        SqlEnum(
            ZoneType,
            name="zone_type_enum",
            native_enum=True,
            create_type=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # HEX-цвет для веб-визуализации радиокарты, формата #RRGGBB.
    # Опционально: если null — UI рендерит дефолтный цвет по типу зоны.
    display_color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    fingerprints: Mapped[list[Fingerprint]] = relationship(
        back_populates="zone",
        passive_deletes=True,
    )
    attendance_logs: Mapped[list[AttendanceLog]] = relationship(
        back_populates="zone",
    )

    __table_args__ = (
        Index("ix_zones_type", "type"),
        # CHECK на формат HEX-цвета через regex Postgres (`~`).
        # Если поле null — пропускаем проверку.
        CheckConstraint(
            "display_color IS NULL OR display_color ~ '^#[0-9A-Fa-f]{6}$'",
            name="display_color_hex",
        ),
    )
