"""Контракт репозитория радиоотпечатков.

Use cases (`application/radiomap/`) работают через этот Protocol,
не зная о SQLAlchemy. Реализация — в
`infrastructure/repositories/fingerprints_repository.py`.

Метод `list_calibrated_for_zone` заложен для будущего ML-классификатора
(следующая веха): он получит набор всех калибровочных отпечатков
конкретной зоны для обучения.
"""

from __future__ import annotations

# Алиас для встроенного list в return-типе list_calibrated_for_zone:
# метод `list` ниже в Protocol затеняет имя при mypy-резолвинге
# forward-references (mypy strict путает type-аннотацию с self-методом).
from builtins import list as List
from datetime import datetime
from typing import Protocol

from app.domain.radiomap.entities import Fingerprint


class FingerprintRepository(Protocol):
    """Контракт хранилища радиоотпечатков. Не зависит от SQLAlchemy."""

    async def add(self, fingerprint: Fingerprint) -> Fingerprint:
        """Создаёт новый отпечаток. Возвращает Fingerprint с заполненным id."""
        ...

    async def get_by_id(self, fingerprint_id: int) -> Fingerprint | None:
        """Возвращает отпечаток или None, если не найден."""
        ...

    async def list(
        self,
        *,
        employee_id: int | None = None,
        zone_id: int | None = None,
        is_calibration: bool | None = None,
        captured_from: datetime | None = None,
        captured_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Fingerprint]:
        """Список отпечатков по фильтрам с пагинацией.

        Все фильтры комбинируются через AND. None означает «не фильтровать».
        Сортировка — по captured_at DESC (новейшие первыми).
        """
        ...

    async def count(
        self,
        *,
        employee_id: int | None = None,
        zone_id: int | None = None,
        is_calibration: bool | None = None,
        captured_from: datetime | None = None,
        captured_to: datetime | None = None,
    ) -> int:
        """Общее количество отпечатков по тем же фильтрам, что и list."""
        ...

    async def delete_by_id(self, fingerprint_id: int) -> bool:
        """Удаляет отпечаток. False если не найден."""
        ...

    async def list_calibrated_for_zone(
        self, zone_id: int
    ) -> List[Fingerprint]:
        """Все калибровочные отпечатки конкретной зоны.

        Заложено для ML-классификатора (следующая веха). Возвращает
        весь набор без пагинации — обучающая выборка обычно невелика
        (десятки точек на зону), весь список умещается в памяти.
        """
        ...
