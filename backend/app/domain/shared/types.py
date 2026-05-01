"""Общие типы и type-aliases для всех доменных модулей.

NewType-обёртки повышают типобезопасность: EmployeeId нельзя случайно
передать там, где ожидается ZoneId, даже если оба — строки.
"""

from __future__ import annotations

from datetime import datetime
from typing import NewType

EmployeeId = NewType("EmployeeId", str)
"""Идентификатор сотрудника (UUID в строковом виде)."""

ZoneId = NewType("ZoneId", str)
"""Идентификатор зоны (workplace, corridor, meeting_room, outside_office)."""

FingerprintId = NewType("FingerprintId", str)
"""Идентификатор радиоотпечатка (UUID)."""

CorrelationId = NewType("CorrelationId", str)
"""Идентификатор корреляции HTTP-запроса (UUID hex без дефисов)."""

Timestamp = datetime
"""Псевдоним для datetime. Используем UTC-aware всюду в домене."""
