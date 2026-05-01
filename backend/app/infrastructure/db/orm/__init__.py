"""ORM-модели проекта.

Импорт всех моделей здесь нужен для двух целей:

1. Регистрация всех таблиц в `Base.metadata` (используется Alembic
   при autogenerate миграций — иначе модели не попадут в diff).
2. Удобный публичный API: `from app.infrastructure.db.orm import Employee`.
"""

from __future__ import annotations

from app.infrastructure.db.orm.attendance import AttendanceLog, AttendanceStatus
from app.infrastructure.db.orm.employees import Employee, Role
from app.infrastructure.db.orm.radiomap import Fingerprint
from app.infrastructure.db.orm.zones import Zone, ZoneType

__all__ = [
    "AttendanceLog",
    "AttendanceStatus",
    "Employee",
    "Fingerprint",
    "Role",
    "Zone",
    "ZoneType",
]
