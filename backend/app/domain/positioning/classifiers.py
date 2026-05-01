"""Контракт классификатора позиции.

Use cases (`application/positioning/`) работают через этот Protocol,
не зная о scikit-learn/numpy. Реализации (`WknnClassifier`,
`RandomForestClassifierImpl`) — в `infrastructure/ml/`.

Это критично для метрологических тестов: сравниваем разные реализации
на одном test set'е через одну и ту же абстракцию.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.positioning.entities import ZoneClassification
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.shared.exceptions import AppError
from app.domain.zones.entities import ZoneType


class TrainingError(AppError):
    """Не удалось обучить классификатор.

    Причины:
    - Пустая калибровочная выборка (не на чем учить)
    - Меньше `MIN_CALIBRATION_POINTS_PER_ZONE` точек в какой-то зоне
    - Попытка classify до train (`is_trained() == False`)

    HTTP 503 Service Unavailable — это проблема конфигурации/наполнения,
    а не пользовательский запрос.
    """

    code = "training_error"
    status_code = 503


class PositionClassifier(Protocol):
    """Единый контракт для всех классификаторов позиции.

    Стейтфул: после `train()` классификатор «помнит» bssid_index и
    обученную модель; `classify()` использует это состояние. Перед
    использованием `is_trained()` должен возвращать True.
    """

    def train(
        self,
        calibration_set: list[Fingerprint],
        zone_types: dict[int, ZoneType],
    ) -> None:
        """Обучает (или переобучает) модель на калибровочной выборке.

        `zone_types` — маппинг `zone_id → ZoneType` для всех зон,
        упоминаемых в калибровке. Передаётся снаружи (из ZoneRepository),
        чтобы classifier мог вернуть полный `ZoneClassification` без
        обращения в БД.

        При недостаточных данных или нарушении инвариантов поднимает
        `TrainingError` с конкретным `code`.
        """
        ...

    def classify(self, observation: RSSIVector) -> ZoneClassification:
        """Классифицирует RSSI-вектор в одну из зон.

        Если `not is_trained()` → `TrainingError(code="not_trained")`.
        """
        ...

    def is_trained(self) -> bool:
        """Готов ли классификатор к классификации."""
        ...
