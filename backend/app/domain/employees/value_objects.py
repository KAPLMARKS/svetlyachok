"""Value objects модуля employees.

Пока — только typed alias для id. Будут добавляться по мере роста
модуля (например, EmailAddress с валидацией формата, если потребуется
домен-уровневая защита от инвалидных значений).
"""

from __future__ import annotations

from typing import NewType

EmployeeId = NewType("EmployeeId", int)
"""Type-safe alias для Employee.id.

Использование в use case:
    def execute(self, employee_id: EmployeeId) -> Employee: ...

mypy будет ругаться, если передать сырой int без cast'а.
"""
