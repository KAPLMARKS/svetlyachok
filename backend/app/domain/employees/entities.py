"""Доменные сущности модуля сотрудников.

Domain ничего не знает об ORM — `Employee` живёт независимо от
SQLAlchemy. Маппер ORM↔domain — забота infrastructure-репозитория.

Role-enum зеркалит ORM-enum (значения должны совпадать строка-в-строку),
но импортов из infrastructure здесь нет — это запрет Clean Architecture.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace
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

    def with_is_active(self, value: bool) -> Employee:
        """Возвращает копию Employee с новым `is_active`.

        Frozen dataclass нельзя мутировать — для смены статуса делаем
        replace. Use cases используют это вместо ручного rebuilding
        всех полей.
        """
        return replace(self, is_active=value)

    def with_password(self, hashed_password: str) -> Employee:
        """Возвращает копию Employee с новым hashed_password.

        Используется в ChangePasswordUseCase: домен не знает о bcrypt,
        получает уже захешированную строку от хешера.
        """
        return replace(self, hashed_password=hashed_password)
