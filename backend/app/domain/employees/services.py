"""Доменные Protocol'ы для сервисов аутентификации.

Эти Protocol'ы живут в domain-слое, чтобы use cases в `application/`
могли получать зависимости через интерфейс, а не через конкретную
реализацию из infrastructure (правило Clean Architecture).
"""

from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    """Контракт хешера паролей. Реализация — в infrastructure/auth/."""

    def hash(self, plain: str) -> str:
        """Захешировать пароль. Возвращает строку (utf-8 декодированный hash)."""
        ...

    def verify(self, plain: str, hashed: str) -> bool:
        """Проверить пароль. Constant-time, безопасно к битым hash'ам."""
        ...
