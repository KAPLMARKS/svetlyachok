"""Извлечение признаков из RSSI-векторов для ML-классификаторов.

Главная задача: преобразовать набор `Fingerprint` (где каждый имеет свой
подмножество BSSID) в плотную row-major numpy-матрицу `[N, M]`, где
M — общее количество уникальных BSSID в калибровочной выборке.

Стабильность порядка BSSID критична: при тренировке формируется
`bssid_index` (sorted), при классификации новый observation
преобразуется по тому же индексу. Иначе позиции колонок не совпадут
и предсказания будут случайными.

Отсутствующий BSSID заполняется `MISSING_RSSI = -100` dBm —
физически это noise floor (нет сигнала).
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from app.core.logging import get_logger
from app.domain.positioning.classifiers import TrainingError
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import BSSID, RSSIVector
from app.infrastructure.ml.config import (
    MIN_CALIBRATION_POINTS_PER_ZONE,
    MISSING_RSSI,
)

log = get_logger(__name__)


def build_feature_matrix(
    calibration_set: list[Fingerprint],
) -> tuple[np.ndarray, np.ndarray, list[BSSID]]:
    """Строит обучающую матрицу из калибровочного набора.

    Возвращает кортеж `(X, y, bssid_index)`:
        - `X`: `np.ndarray[N, M]` row-major float64; rssi-значения
          с заполнением `MISSING_RSSI` для отсутствующих BSSID.
        - `y`: `np.ndarray[N]` int64; zone_id каждой строки.
        - `bssid_index`: упорядоченный (sorted) список BSSID длины M;
          определяет соответствие столбцов X.

    Маппинг `zone_id → ZoneType` получаем отдельно (через
    `ZoneRepository`), не здесь — features.py не зависит от domain
    zones, делает только feature engineering.

    Поднимает `TrainingError` при недостаточных данных:
    - Пустой `calibration_set` → `code="empty_calibration_set"`
    - Найден отпечаток без `zone_id` → `code="invalid_calibration"`
      (защитная проверка: invariant калибровочного отпечатка)
    - В какой-то зоне < `MIN_CALIBRATION_POINTS_PER_ZONE` →
      `code="insufficient_calibration_points"`
    """
    log.debug(
        "[ml.features.build_feature_matrix] start",
        calibration_size=len(calibration_set),
    )

    if not calibration_set:
        raise TrainingError(
            code="empty_calibration_set",
            message="Калибровочная выборка пуста — нечем обучать классификатор",
        )

    # Защита: калибровочный fingerprint без zone_id или zone_type
    # технически невозможен (invariant Fingerprint в domain), но при
    # ошибочной выборке через repo может случиться. Явная проверка.
    for fp in calibration_set:
        if fp.zone_id is None:
            raise TrainingError(
                code="invalid_calibration",
                message=(
                    f"Калибровочный отпечаток id={fp.id} не имеет zone_id. "
                    "Проверьте логику list_calibrated_all в репозитории."
                ),
            )

    # Проверка минимума точек на зону.
    counter = Counter(fp.zone_id for fp in calibration_set)
    insufficient = {
        zid: n for zid, n in counter.items() if n < MIN_CALIBRATION_POINTS_PER_ZONE
    }
    if insufficient:
        raise TrainingError(
            code="insufficient_calibration_points",
            message=(
                f"Недостаточно калибровочных точек в зонах {insufficient}. "
                f"Требуется минимум {MIN_CALIBRATION_POINTS_PER_ZONE} на каждую зону."
            ),
            details={"per_zone_counts": dict(counter), "required_min": MIN_CALIBRATION_POINTS_PER_ZONE},
        )

    # Стабильный sorted bssid_index: сортируем по строковому
    # представлению BSSID. Это даёт воспроизводимый порядок столбцов
    # между запусками (требование к экспериментам).
    all_bssids: set[BSSID] = set()
    for fp in calibration_set:
        all_bssids.update(fp.rssi_vector.bssids())
    bssid_index: list[BSSID] = sorted(all_bssids, key=lambda b: b.value)
    bssid_to_col: dict[BSSID, int] = {b: i for i, b in enumerate(bssid_index)}

    n_samples = len(calibration_set)
    n_features = len(bssid_index)

    # Инициализация заполнителем `MISSING_RSSI` — отсутствующие точки
    # доступа в данном fingerprint'е получат noise floor.
    X = np.full((n_samples, n_features), float(MISSING_RSSI), dtype=np.float64)
    y = np.zeros(n_samples, dtype=np.int64)

    for row_idx, fp in enumerate(calibration_set):
        for bssid, dbm in fp.rssi_vector.samples.items():
            X[row_idx, bssid_to_col[bssid]] = float(dbm)
        # Type-narrowing: zone_id проверен выше, не None.
        assert fp.zone_id is not None
        y[row_idx] = fp.zone_id

    log.info(
        "[ml.features.build_feature_matrix] done",
        n_samples=n_samples,
        n_features=n_features,
        n_zones=len({int(zid) for zid in y}),
    )
    return X, y, bssid_index


def build_observation_vector(
    observation: RSSIVector,
    bssid_index: list[BSSID],
) -> np.ndarray:
    """Строит feature-вектор `[1, M]` для классификации.

    Использует тот же `bssid_index`, что был зафиксирован при тренировке.
    Новые BSSID (которых не было в калибровочной выборке) ИГНОРИРУЮТСЯ —
    добавлять их нельзя, иначе нарушится контракт «модель обучена на
    M фичах».

    Отсутствующие в observation BSSID из bssid_index заполняются
    `MISSING_RSSI` (noise floor).
    """
    if not bssid_index:
        raise TrainingError(
            code="not_trained",
            message="bssid_index пуст — классификатор не обучен",
        )

    n_features = len(bssid_index)
    vec = np.full((1, n_features), float(MISSING_RSSI), dtype=np.float64)

    bssid_to_col = {b: i for i, b in enumerate(bssid_index)}
    known = 0
    unknown = 0
    for bssid, dbm in observation.samples.items():
        if bssid in bssid_to_col:
            vec[0, bssid_to_col[bssid]] = float(dbm)
            known += 1
        else:
            unknown += 1

    log.debug(
        "[ml.features.build_observation_vector] done",
        n_features=n_features,
        known_bssids=known,
        unknown_bssids=unknown,
    )
    return vec
