"""Контракт репозитория записей учёта посещаемости.

Use cases (`application/attendance/`) работают через этот Protocol,
не зная о SQLAlchemy. Реализация — в
`infrastructure/repositories/attendance_repository.py`.

`get_open_session_for_employee` использует partial-index
`ix_attendance_logs_open_sessions` для быстрого ответа: открытых
сессий мало (≤ численности сотрудников).
"""

from __future__ import annotations

# Алиас для встроенного list — метод `list` ниже затеняет имя при mypy
# strict, и forward references в type-аннотациях ломаются. То же решение
# использовано в FingerprintRepository.
from builtins import list as List
from datetime import datetime
from typing import Protocol

from app.domain.attendance.entities import AttendanceLog
from app.domain.attendance.value_objects import AttendanceStatus


class AttendanceRepository(Protocol):
    """Контракт хранилища записей посещаемости. Не зависит от SQLAlchemy."""

    async def add(self, log: AttendanceLog) -> AttendanceLog:
        """Создаёт новую запись. Возвращает AttendanceLog с заполненным id."""
        ...

    async def update(self, log: AttendanceLog) -> AttendanceLog:
        """Обновляет существующую запись (close/extend) и возвращает её.

        Использует `log.id` для идентификации. Поднимает `NotFoundError`,
        если записи с таким id не существует.
        """
        ...

    async def get_by_id(self, log_id: int) -> AttendanceLog | None:
        """Возвращает запись или None, если не найдена."""
        ...

    async def get_open_session_for_employee(
        self, employee_id: int
    ) -> AttendanceLog | None:
        """Возвращает текущую открытую сессию (`ended_at IS NULL`) сотрудника.

        Если открытых нет — возвращает None. Если их несколько (теоретически
        не должно быть при корректной работе RecordAttendanceUseCase, но
        возможно после рестартов с гонкой) — возвращает самую свежую по
        `started_at`.
        """
        ...

    async def list(
        self,
        *,
        employee_id: int | None = None,
        zone_id: int | None = None,
        status: AttendanceStatus | None = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AttendanceLog]:
        """Список записей по фильтрам с пагинацией.

        Все фильтры комбинируются через AND. None означает «не фильтровать».
        Сортировка — по `started_at` DESC (новейшие первыми).
        """
        ...

    async def count(
        self,
        *,
        employee_id: int | None = None,
        zone_id: int | None = None,
        status: AttendanceStatus | None = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
    ) -> int:
        """Общее количество записей по тем же фильтрам, что и list."""
        ...
