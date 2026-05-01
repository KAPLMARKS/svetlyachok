"""
Шаблон извлечения признаков из RSSI-радиоотпечатков для классификаторов.

Используется в `backend/app/infrastructure/ml/features.py`.

Принципы:
- MISSING_RSSI = -100 для отсутствующих BSSID
- Глобальный список BSSID кешируется при первом обучении
- Возвращаются numpy-массивы X (samples × features) и y (labels)
- НЕ нормализовать здесь — пусть классификатор решает (KNN не любит scaling, RF индифферентен)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog

# Из доменной модели импортировать соответствующие типы.
# Здесь указано как пример — адаптировать под ваши классы.
# from app.domain.radiomap.entities import Fingerprint
# from app.domain.radiomap.value_objects import RSSIVector

log = structlog.get_logger(__name__)

MISSING_RSSI: int = -100
"""
Значение, заполняемое для BSSID, не наблюдаемой в данном измерении.
Выбрано как "ниже минимально различимой мощности". -100 dBm соответствует
теоретическому пределу слышимости для большинства смартфонов.
"""


@dataclass(frozen=True)
class FeatureMatrix:
    """Подготовленный набор признаков для классификатора."""

    X: np.ndarray  # shape (n_samples, n_bssids), dtype=int16
    y: np.ndarray | None  # shape (n_samples,), dtype=object (zone labels). None для test без labels
    bssid_index: tuple[str, ...]  # упорядоченный список BSSID, соответствует столбцам X


def build_feature_matrix(
    fingerprints: list,  # list[Fingerprint] из доменной модели
    *,
    bssid_index: tuple[str, ...] | None = None,
    include_labels: bool = True,
) -> FeatureMatrix:
    """
    Преобразует список радиоотпечатков в плотную матрицу признаков для классификатора.

    Если `bssid_index` передан — используется как фиксированный набор столбцов
    (для test-сета должен совпадать с тренировочным). Иначе — собирается из всех
    наблюдаемых BSSID в `fingerprints` (для тренировочного сета).

    Args:
        fingerprints: список доменных Fingerprint с полями `.rssi_vector` и `.zone_label`.
        bssid_index: упорядоченный кортеж BSSID для столбцов матрицы.
                     None означает "построить из данных" (только для train).
        include_labels: вернуть ли вектор меток `y`.

    Returns:
        FeatureMatrix с X, y, bssid_index.
    """
    if not fingerprints:
        raise ValueError("[features.build_feature_matrix] fingerprints is empty")

    # 1. Если bssid_index не задан — собрать из всех наблюдений (train mode)
    if bssid_index is None:
        all_bssids: set[str] = set()
        for fp in fingerprints:
            for obs in fp.rssi_vector.observations:
                all_bssids.add(obs.bssid.value)
        bssid_index = tuple(sorted(all_bssids))
        log.debug(
            "[features.build_feature_matrix] built bssid_index from train set",
            bssid_count=len(bssid_index),
        )
    else:
        log.debug(
            "[features.build_feature_matrix] reuse bssid_index from train",
            bssid_count=len(bssid_index),
        )

    # 2. Заполнение матрицы X
    n_samples = len(fingerprints)
    n_features = len(bssid_index)
    X = np.full((n_samples, n_features), fill_value=MISSING_RSSI, dtype=np.int16)

    bssid_to_col = {bssid: idx for idx, bssid in enumerate(bssid_index)}

    for row_idx, fp in enumerate(fingerprints):
        for obs in fp.rssi_vector.observations:
            col_idx = bssid_to_col.get(obs.bssid.value)
            if col_idx is None:
                # BSSID, не виденный на тренировке — игнорируем (test может содержать новые APs)
                continue
            X[row_idx, col_idx] = obs.rssi_dbm

    # 3. Извлечение меток
    y: np.ndarray | None = None
    if include_labels:
        labels = [fp.zone_label for fp in fingerprints]
        y = np.array(labels, dtype=object)

    log.debug(
        "[features.build_feature_matrix] done",
        n_samples=n_samples,
        n_features=n_features,
        density_pct=round(100 * float(np.sum(X != MISSING_RSSI)) / X.size, 2),
    )

    return FeatureMatrix(X=X, y=y, bssid_index=bssid_index)


def filter_weak_signals(
    fingerprints: list,  # list[Fingerprint]
    threshold_dbm: int = -85,
) -> list:
    """
    Опциональный pre-filter: убирает наблюдения с RSSI < threshold.

    Слабые сигналы более шумные, и их фильтрация иногда улучшает точность.
    Использовать осознанно — на сравнительных тестах с/без фильтра.

    Args:
        fingerprints: исходный список.
        threshold_dbm: порог в dBm. Наблюдения < threshold_dbm удаляются.

    Returns:
        Новый список Fingerprint без слабых наблюдений.
    """
    filtered = []
    removed_count = 0
    for fp in fingerprints:
        strong_obs = tuple(
            obs for obs in fp.rssi_vector.observations if obs.rssi_dbm >= threshold_dbm
        )
        removed_count += len(fp.rssi_vector.observations) - len(strong_obs)
        # Если в отпечатке не осталось наблюдений — пропустить целиком (бессмысленно классифицировать)
        if not strong_obs:
            continue
        # Создать новый Fingerprint с фильтрованным RSSIVector (адаптировать под domain model)
        # filtered_fp = fp.with_observations(strong_obs)  # пример API
        # filtered.append(filtered_fp)
        # Для шаблона — оставить как есть, так как точная сигнатура зависит от ваших моделей
        filtered.append(fp)

    log.debug(
        "[features.filter_weak_signals] done",
        threshold_dbm=threshold_dbm,
        observations_removed=removed_count,
        fingerprints_remaining=len(filtered),
    )

    return filtered
