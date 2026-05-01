"""Доменные сущности модуля positioning."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.positioning.value_objects import Confidence
from app.domain.zones.entities import ZoneType


@dataclass(frozen=True)
class ZoneClassification:
    """Результат классификации позиции — предсказанная зона + confidence.

    `classifier_name` хранит имя реализации (`wknn` / `random_forest`)
    для логирования, A/B-сравнений и метрологических отчётов
    (важно для главы «Метрологические результаты» диссертации).
    """

    zone_id: int
    zone_type: ZoneType
    confidence: Confidence
    classifier_name: str
