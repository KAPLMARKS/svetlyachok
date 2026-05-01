"""Гиперпараметры ML-классификаторов и общие константы.

Все значения версионируются в git для воспроизводимости экспериментов
ISO/IEC 18305:2016. Изменение значений инвалидирует все ранее обученные
модели и эталонные метрики в `tests/ml/`; необходим rerun метрологических
тестов и фиксация новых эталонов.

Random seeds зафиксированы (`random_state=42`), поэтому повторные
запуски на одних и тех же данных дают идентичные результаты.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# RSSI noise floor: значение для отсутствующих BSSID в feature-векторе.
# Wi-Fi RSSI физически не опускается ниже этого порога — для
# отсутствующего сигнала это семантически верно.
MISSING_RSSI: int = -100


# Минимум калибровочных точек на одну зону для обучения KNN.
# При k=3 нужно как минимум 3 точки в каждой зоне; иначе
# KNeighborsClassifier выдаст ошибку при fit.
MIN_CALIBRATION_POINTS_PER_ZONE: int = 3


@dataclass(frozen=True)
class WknnConfig:
    """Гиперпараметры WKNN-классификатора.

    Параметры по умолчанию:
    - `n_neighbors=3` — стандарт для indoor positioning при плотной
      калибровочной сетке (3-7 типично).
    - `weights="distance"` — это и есть «W» в WKNN. НЕ путать с
      `"uniform"` (обычный KNN); по умолчанию sklearn использует uniform.
    - `metric="euclidean"` — базовый выбор. Для RSSI также применяют
      `cityblock` (Manhattan) и `chebyshev`; сравним в полевых
      испытаниях после сбора реальных данных.
    """

    n_neighbors: int = 3
    weights: Literal["distance"] = "distance"
    metric: Literal["euclidean", "cityblock", "chebyshev"] = "euclidean"


@dataclass(frozen=True)
class RandomForestConfig:
    """Гиперпараметры Random Forest-классификатора.

    Параметры по умолчанию:
    - `n_estimators=100` — стандарт для table'ных задач; baseline.
    - `max_depth=None` — пусть деревья растут до min_samples_split.
    - `min_samples_split=2` — sklearn default.
    - `class_weight="balanced"` — ВАЖНО: калибровочные точки обычно
      распределены неравномерно по зонам (одни помещения покрыты
      плотнее других). balanced компенсирует через инверсные частоты.
    - `random_state=42` — фиксированный seed для воспроизводимости
      между запусками (требование ISO/IEC 18305 экспериментов).
    """

    n_estimators: int = 100
    max_depth: int | None = None
    min_samples_split: int = 2
    class_weight: Literal["balanced"] = "balanced"
    random_state: int = 42
