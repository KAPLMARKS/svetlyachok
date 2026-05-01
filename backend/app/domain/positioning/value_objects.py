"""Value objects модуля positioning.

`Confidence` — нормализованная вероятность классификации, всегда в
диапазоне `[0.0, 1.0]`. Используется как поле `ZoneClassification`
для отображения уверенности классификатора.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.shared.exceptions import ValidationError


@dataclass(frozen=True)
class Confidence:
    """Уверенность классификатора в предсказании ([0.0, 1.0]).

    Frozen, value-based equality. Безопасен как поле dataclass'а.
    """

    value: float

    def __post_init__(self) -> None:
        # bool наследник int — не путать с float; явный отказ.
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ValidationError(
                code="invalid_confidence_type",
                message=(
                    f"Confidence должен быть float, получено "
                    f"{type(self.value).__name__}"
                ),
            )
        if self.value < 0.0 or self.value > 1.0:
            raise ValidationError(
                code="confidence_out_of_range",
                message=(
                    f"Confidence {self.value} вне диапазона [0.0, 1.0]. "
                    "Проверь нормализацию вероятностей классификатора."
                ),
            )

    def __float__(self) -> float:
        return float(self.value)
