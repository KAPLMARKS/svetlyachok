"""Pydantic-схемы эндпоинта классификации позиции."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

_RSSI_VECTOR_FIELD = Annotated[
    dict[str, int],
    Field(
        description="Карта BSSID → dBm. BSSID нормализуется на сервере.",
        min_length=1,
        max_length=200,
        examples=[{"AA:BB:CC:DD:EE:01": -45, "AA:BB:CC:DD:EE:02": -67}],
    ),
]


class ClassifyRequest(BaseModel):
    """POST /api/v1/positioning/classify — классифицировать RSSI-вектор."""

    model_config = ConfigDict(extra="forbid")

    rssi_vector: _RSSI_VECTOR_FIELD


class ClassifyResponse(BaseModel):
    """Результат классификации.

    `classifier_name` показывает, какая реализация дала ответ
    (`wknn` / `random_forest`). На пилоте используется одна
    конфигурация, но клиенту полезно знать — для логирования и A/B.
    """

    model_config = ConfigDict(extra="forbid")

    zone_id: int
    zone_type: str
    confidence: float
    classifier_name: str
