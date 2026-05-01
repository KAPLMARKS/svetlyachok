"""In-memory fakes для unit-тестов use cases.

Реализуют domain Protocols без БД, с явным auto-increment id.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.employees.entities import Employee, Role
from app.domain.radiomap.entities import Fingerprint
from app.domain.shared.exceptions import ConflictError, NotFoundError
from app.domain.zones.entities import Zone, ZoneType


class FakeEmployeeRepository:
    """In-memory EmployeeRepository.

    Совместим по сигнатурам с domain Protocol — duck-typing.
    Симулирует unique-constraint на email и FK NotFoundError.
    """

    def __init__(self) -> None:
        self._storage: dict[int, Employee] = {}
        self._next_id = 1

    async def get_by_id(self, employee_id: int) -> Employee | None:
        return self._storage.get(employee_id)

    async def get_by_email(self, email: str) -> Employee | None:
        for emp in self._storage.values():
            if emp.email == email:
                return emp
        return None

    async def list(
        self,
        *,
        role: Role | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Employee]:
        items = sorted(self._storage.values(), key=lambda e: e.id)
        items = self._apply_filters(items, role=role, is_active=is_active)
        return items[offset : offset + limit]

    async def count(
        self,
        *,
        role: Role | None = None,
        is_active: bool | None = None,
    ) -> int:
        items = list(self._storage.values())
        return len(self._apply_filters(items, role=role, is_active=is_active))

    async def add(self, employee: Employee) -> Employee:
        if any(e.email == employee.email for e in self._storage.values()):
            raise ConflictError(
                code="employee_email_taken",
                message=f"Email {employee.email!r} занят",
            )
        new_id = self._next_id
        self._next_id += 1
        stored = replace(employee, id=new_id)
        self._storage[new_id] = stored
        return stored

    async def update(self, employee: Employee) -> Employee:
        if employee.id not in self._storage:
            raise NotFoundError(
                code="employee_not_found",
                message=f"id={employee.id}",
            )
        # Симулируем unique-проверку: если новый email совпадает с
        # email чужой записи — ConflictError.
        for other in self._storage.values():
            if other.id != employee.id and other.email == employee.email:
                raise ConflictError(
                    code="employee_email_taken",
                    message=f"Email {employee.email!r} занят",
                )
        self._storage[employee.id] = employee
        return employee

    @staticmethod
    def _apply_filters(
        items: list[Employee],
        *,
        role: Role | None,
        is_active: bool | None,
    ) -> list[Employee]:
        if role is not None:
            items = [e for e in items if e.role is role]
        if is_active is not None:
            items = [e for e in items if e.is_active == is_active]
        return items


class FakeZoneRepository:
    """In-memory ZoneRepository.

    Симулирует unique-constraint на name. Для имитации FK RESTRICT
    можно добавить через флаг `force_zone_in_use_on_delete` —
    используем в тесте delete.
    """

    def __init__(self) -> None:
        self._storage: dict[int, Zone] = {}
        self._next_id = 1
        # Множество zone_id, которые при попытке удаления должны
        # выкинуть ConflictError(zone_in_use).
        self._zones_in_use: set[int] = set()

    def mark_in_use(self, zone_id: int) -> None:
        """Тестовая утилита: пометить зону как «используется» для
        проверки поведения delete_by_id при FK RESTRICT."""
        self._zones_in_use.add(zone_id)

    async def get_by_id(self, zone_id: int) -> Zone | None:
        return self._storage.get(zone_id)

    async def get_by_name(self, name: str) -> Zone | None:
        for z in self._storage.values():
            if z.name == name:
                return z
        return None

    async def list(
        self,
        *,
        type_filter: ZoneType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Zone]:
        items = sorted(self._storage.values(), key=lambda z: z.id)
        if type_filter is not None:
            items = [z for z in items if z.type is type_filter]
        return items[offset : offset + limit]

    async def count(self, *, type_filter: ZoneType | None = None) -> int:
        items = list(self._storage.values())
        if type_filter is not None:
            items = [z for z in items if z.type is type_filter]
        return len(items)

    async def add(self, zone: Zone) -> Zone:
        if any(z.name == zone.name for z in self._storage.values()):
            raise ConflictError(
                code="zone_name_taken",
                message=f"Имя {zone.name!r} занято",
            )
        new_id = self._next_id
        self._next_id += 1
        stored = replace(zone, id=new_id)
        self._storage[new_id] = stored
        return stored

    async def update(self, zone: Zone) -> Zone:
        if zone.id not in self._storage:
            raise NotFoundError(
                code="zone_not_found",
                message=f"id={zone.id}",
            )
        for other in self._storage.values():
            if other.id != zone.id and other.name == zone.name:
                raise ConflictError(
                    code="zone_name_taken",
                    message=f"Имя {zone.name!r} занято",
                )
        self._storage[zone.id] = zone
        return zone

    async def delete_by_id(self, zone_id: int) -> bool:
        if zone_id not in self._storage:
            return False
        if zone_id in self._zones_in_use:
            raise ConflictError(
                code="zone_in_use",
                message=f"Зона id={zone_id} используется",
                details={"reason": "attendance_logs_exist"},
            )
        del self._storage[zone_id]
        return True


class FakeFingerprintRepository:
    """In-memory FingerprintRepository.

    Поддерживает все методы Protocol'а, включая фильтры и сортировку
    по captured_at DESC. `list_calibrated_for_zone` использует
    фильтр zone_id + is_calibration=True.
    """

    def __init__(self) -> None:
        self._storage: dict[int, Fingerprint] = {}
        self._next_id = 1

    async def add(self, fingerprint: Fingerprint) -> Fingerprint:
        new_id = self._next_id
        self._next_id += 1
        stored = replace(fingerprint, id=new_id)
        self._storage[new_id] = stored
        return stored

    async def get_by_id(self, fingerprint_id: int) -> Fingerprint | None:
        return self._storage.get(fingerprint_id)

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
    ) -> list[Fingerprint]:
        items = self._apply_filters(
            list(self._storage.values()),
            employee_id=employee_id,
            zone_id=zone_id,
            is_calibration=is_calibration,
            captured_from=captured_from,
            captured_to=captured_to,
        )
        items.sort(key=lambda fp: fp.captured_at, reverse=True)
        return items[offset : offset + limit]

    async def count(
        self,
        *,
        employee_id: int | None = None,
        zone_id: int | None = None,
        is_calibration: bool | None = None,
        captured_from: datetime | None = None,
        captured_to: datetime | None = None,
    ) -> int:
        items = self._apply_filters(
            list(self._storage.values()),
            employee_id=employee_id,
            zone_id=zone_id,
            is_calibration=is_calibration,
            captured_from=captured_from,
            captured_to=captured_to,
        )
        return len(items)

    async def delete_by_id(self, fingerprint_id: int) -> bool:
        if fingerprint_id not in self._storage:
            return False
        del self._storage[fingerprint_id]
        return True

    async def list_calibrated_for_zone(self, zone_id: int) -> list[Fingerprint]:
        return [
            fp
            for fp in self._storage.values()
            if fp.zone_id == zone_id and fp.is_calibration
        ]

    @staticmethod
    def _apply_filters(
        items: list[Fingerprint],
        *,
        employee_id: int | None,
        zone_id: int | None,
        is_calibration: bool | None,
        captured_from: datetime | None,
        captured_to: datetime | None,
    ) -> list[Fingerprint]:
        if employee_id is not None:
            items = [fp for fp in items if fp.employee_id == employee_id]
        if zone_id is not None:
            items = [fp for fp in items if fp.zone_id == zone_id]
        if is_calibration is not None:
            items = [fp for fp in items if fp.is_calibration == is_calibration]
        if captured_from is not None:
            items = [fp for fp in items if fp.captured_at >= captured_from]
        if captured_to is not None:
            items = [fp for fp in items if fp.captured_at <= captured_to]
        return items
