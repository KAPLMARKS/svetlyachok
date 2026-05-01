"""Pydantic-схемы радиоотпечатков и калибровочных точек."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

_RSSI_VECTOR_FIELD = Annotated[
    dict[str, int],
    Field(
        description="Карта BSSID → dBm. BSSID нормализуется на сервере.",
        min_length=1,
        max_length=200,
        examples=[{"AA:BB:CC:DD:EE:01": -45, "AA:BB:CC:DD:EE:02": -67}],
    ),
]


class FingerprintSubmitRequest(BaseModel):
    """POST /api/v1/fingerprints — приём live-замера от устройства."""

    model_config = ConfigDict(extra="forbid")

    captured_at: AwareDatetime = Field(
        ...,
        description="Время замера (timezone-aware, предпочтительно UTC).",
    )
    rssi_vector: _RSSI_VECTOR_FIELD
    sample_count: int = Field(default=1, ge=1, le=100)
    device_id: str | None = Field(default=None, max_length=64)


class CalibrationPointCreateRequest(BaseModel):
    """POST /api/v1/calibration/points — admin создаёт эталонную точку."""

    model_config = ConfigDict(extra="forbid")

    zone_id: int = Field(..., gt=0)
    captured_at: AwareDatetime
    rssi_vector: _RSSI_VECTOR_FIELD
    sample_count: int = Field(default=1, ge=1, le=100)
    device_id: str | None = Field(default=None, max_length=64)


class FingerprintResponse(BaseModel):
    """Публичная информация о радиоотпечатке."""

    model_config = ConfigDict(extra="forbid")

    id: int
    employee_id: int | None
    zone_id: int | None
    is_calibration: bool
    captured_at: datetime
    device_id: str | None
    rssi_vector: dict[str, int]
    sample_count: int


class FingerprintsPageResponse(BaseModel):
    """Страница отпечатков с пагинацией."""

    model_config = ConfigDict(extra="forbid")

    items: list[FingerprintResponse]
    total: int
    limit: int
    offset: int
