"""Доменная сущность `Fingerprint`.

Domain-уровень не знает об ORM или JSONB — `rssi_vector` хранится как
`RSSIVector` value object. Маппер ORM ↔ domain — забота
infrastructure-репозитория.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from app.domain.radiomap.value_objects import RSSIVector
from app.domain.shared.exceptions import ValidationError


@dataclass(frozen=True)
class Fingerprint:
    """RSSI-радиоотпечаток.

    Два режима:

    - **Калибровочный** (`is_calibration=True`): эталонная точка от
      admin'а. ОБЯЗАН иметь `zone_id` (зеркалит DB CHECK
      calibration_requires_zone).
    - **Live** (`is_calibration=False`): замер с устройства сотрудника.
      `zone_id` может быть `None` до классификации.

    Frozen — после создания не мутируется; обновление через
    `with_zone` или `replace`.
    """

    id: int
    employee_id: int | None
    zone_id: int | None
    is_calibration: bool
    captured_at: datetime
    device_id: str | None
    rssi_vector: RSSIVector
    sample_count: int

    def __post_init__(self) -> None:
        # Доменный инвариант — зеркалит CHECK calibration_requires_zone
        # в БД. Реализация repository тоже его проверит, но domain
        # ловит раньше — улучшая сообщение об ошибке.
        if self.is_calibration and self.zone_id is None:
            raise ValidationError(
                code="calibration_requires_zone",
                message="Калибровочный отпечаток обязан быть привязан к зоне",
            )
        if self.sample_count < 1:
            raise ValidationError(
                code="sample_count_must_be_positive",
                message=f"sample_count должен быть >= 1, получено {self.sample_count}",
            )
        if self.captured_at.tzinfo is None:
            raise ValidationError(
                code="captured_at_must_be_timezone_aware",
                message="captured_at обязан быть timezone-aware (предпочтительно UTC)",
            )

    def with_zone(self, zone_id: int | None) -> Fingerprint:
        """Возвращает копию с обновлённым `zone_id` (например, после
        классификации live-отпечатка)."""
        return replace(self, zone_id=zone_id)
