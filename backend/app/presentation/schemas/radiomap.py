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


class FingerprintBulkSubmitRequest(BaseModel):
    """POST /api/v1/fingerprints/batch — пачка live-замеров от mobile.

    Limit 100 — компромисс под Android WorkManager-throttling
    (~60 сканов/час) с небольшим запасом на длительный офлайн.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[FingerprintSubmitRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Массив отпечатков, до 100 штук за запрос.",
    )


class BulkAcceptedItem(BaseModel):
    """Запись об успешно сохранённом отпечатке в bulk-ответе."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=0, description="Индекс item'а в исходном items[].")
    fingerprint: FingerprintResponse


class BulkRejectedItem(BaseModel):
    """Запись об отклонённом отпечатке в bulk-ответе.

    `code` совпадает с `AppError.code` (например, `captured_at_in_future`),
    чтобы mobile-клиент мог решить: удалять локальную запись или оставить
    для retry.
    """

    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=0, description="Индекс item'а в исходном items[].")
    code: str
    message: str


class FingerprintBulkSubmitResponse(BaseModel):
    """Ответ на bulk-приём — partial success.

    `accepted_count + rejected_count == len(items)` всегда.
    Mobile удаляет из sqflite-кэша записи по `accepted[].index`,
    rejected — анализирует код и решает (удалить как нерешаемую ошибку
    или оставить для retry).
    """

    model_config = ConfigDict(extra="forbid")

    accepted: list[BulkAcceptedItem]
    rejected: list[BulkRejectedItem]
    accepted_count: int = Field(..., ge=0)
    rejected_count: int = Field(..., ge=0)
