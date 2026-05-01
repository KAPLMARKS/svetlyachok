"""Доменные сущности модуля сотрудников.

Domain ничего не знает об ORM — `Employee` живёт независимо от
SQLAlchemy. Маппер ORM↔domain — забота infrastructure-репозитория.

Role-enum зеркалит ORM-enum (значения должны совпадать строка-в-строку),
но импортов из infrastructure здесь нет — это запрет Clean Architecture.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import time


class Role(str, enum.Enum):
    """Роли пользователей. Значения совпадают с ORM RoleEnum."""

    ADMIN = "admin"
    EMPLOYEE = "employee"


@dataclass(frozen=True)
class Employee:
    """Сотрудник системы — корневая сущность модуля employees.

    Frozen: после получения из репозитория мутировать нельзя; любое
    изменение проходит через use case → новый Employee → save в repo.

    `hashed_password` — bcrypt-hash, сравнивается через `PasswordHasher.verify`.
    Никогда не возвращается клиенту (см. `presentation/schemas/auth.py:CurrentUserResponse`).
    """

    id: int
    email: str
    full_name: str
    role: Role
    hashed_password: str
    is_active: bool
    schedule_start: time | None = None
    schedule_end: time | None = None

    def is_admin(self) -> bool:
        """Удобный shortcut для авторизационных проверок в use cases."""
        return self.role is Role.ADMIN
