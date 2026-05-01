---
name: wifi-rssi-wknn
description: >-
  Domain expertise for indoor positioning via Wi-Fi RSSI fingerprinting using
  Weighted K-Nearest Neighbors (WKNN) and Random Forest classifiers. Use this
  skill when implementing, reviewing, tuning, or documenting code that
  collects RSSI vectors from Wi-Fi access points, builds a calibration
  radiomap, classifies indoor zones (workplace, corridor, meeting room,
  outside-office), or evaluates positioning accuracy per ISO/IEC 18305:2016
  (RMSE, Detection Probability). Triggers on tasks involving RSSI, BSSID,
  fingerprinting, WKNN, KNN, Random Forest, indoor positioning, IPS, IoT
  attendance tracking. Methodology is fixed for the АИС «Светлячок» diploma
  project — see project ARCHITECTURE.md.
license: MIT
metadata:
  author: aif-skill-generator
  version: "1.0.0"
  category: machine-learning
  domain: indoor-positioning
---

# Wi-Fi RSSI Fingerprinting + WKNN/Random Forest

Domain-specific экспертиза для проекта АИС «Светлячок» — internal positioning system, использующий уровень принимаемого сигнала Wi-Fi (RSSI) от стандартных корпоративных точек доступа для классификации зон местоположения сотрудника без дополнительной аппаратуры.

Методология зафиксирована в `.ai-factory/DESCRIPTION.md` и `.ai-factory/ARCHITECTURE.md`. Этот скилл — компактный набор правил и паттернов для работы с RSSI-данными и алгоритмами WKNN/Random Forest.

## Когда применять

- Реализация или ревью кода в `backend/app/ml/` (классификаторы, извлечение признаков, метрики)
- Реализация или ревью кода в `backend/app/domain/positioning/` и `backend/app/domain/radiomap/` (доменные модели для RSSI-векторов и калибровочных точек)
- Endpoint-ы приёма радиоотпечатков, калибровки радиокарты, классификации позиции
- Экспериментальная часть (полевые испытания, метрологические тесты, оптимизация гиперпараметров)
- Любая работа с RSSI-сигналами, BSSID-векторами, индорным позиционированием

## Когда НЕ применять

- Outdoor GPS/ГЛОНАСС (не наша область)
- BLE-маяки, RTT/FTM, ультразвук — отвергнуты на этапе проектирования
- Магнитное поле / IMU sensor fusion — исключено из методологии диплома
- iOS — не поддерживается (см. project memory о NEHotspotHelper entitlement)

## Ключевые принципы

### 1. Воспроизводимость экспериментов важнее производительности

Это исследовательский проект. Каждое измерение RMSE и Detection Probability должно быть воспроизводимо побитово. Поэтому:

- Все гиперпараметры (`k`, `weights`, `metric`, `n_estimators`, `max_depth`, `random_state`) хранятся в `infrastructure/ml/config.py` и версионируются в git
- Random seeds (NumPy, scikit-learn) фиксируются явно: `np.random.seed(42)`, `RandomForestClassifier(..., random_state=42)`
- Калибровочные данные (тренировочный сет) и тестовые сеты сохраняются как отдельные артефакты с версионированием (`data/calibration_v{n}.parquet`)
- Каждый эксперимент сохраняет конфигурацию + метрики в JSON-файл (`ml-artifacts/experiment_{timestamp}.json`)

### 2. RSSI — это **отрицательное** число в децибелах (dBm)

- Типичные значения: −30 dBm (очень близко) до −90 dBm (на границе слышимости)
- −100 dBm и ниже — точка не видна (отсутствие сигнала)
- НЕ преобразовывать в положительные числа — это ломает физическую интерпретацию
- Для отсутствующих BSSID в векторе использовать значение `MISSING_RSSI = -100` (или `np.nan`, в зависимости от классификатора)
- НЕ путать с SNR (signal-to-noise ratio) — это другая метрика

### 3. Радиоотпечаток — это разреженный вектор

- Полный набор BSSID в здании может быть 50–500. В каждом измерении видно только 5–20 точек.
- Хранить как dict `{bssid: rssi}` в Python / JSONB в PostgreSQL для удобства
- Преобразовывать в плотный вектор только при подаче в классификатор: row-major матрица `[N_samples, N_bssids]` с `MISSING_RSSI` для отсутствующих
- Глобальный список BSSID фиксировать на этапе обучения и хранить в модели — иначе test-сет будет несовместим

### 4. WKNN — это KNN с distance-weighting

- Использовать `sklearn.neighbors.KNeighborsClassifier(n_neighbors=k, weights="distance", metric="euclidean")`
- НЕ путать `weights="distance"` (наш WKNN) с `weights="uniform"` (обычный KNN). По умолчанию sklearn использует uniform.
- Метрика расстояния по умолчанию — Euclidean. Для RSSI-фингерпринтинга также применяют `cityblock` (Manhattan) и `chebyshev`. Сравнить в экспериментах.
- Оптимальное `k` для indoor-позиционирования обычно 3–7. Зависит от плотности калибровочной сетки.

### 5. Random Forest — это baseline для сравнения с WKNN

- В диссертации сравниваем точность WKNN vs Random Forest на одинаковом тест-сете
- Использовать `sklearn.ensemble.RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced")`
- `n_estimators` 50–200, `max_depth` 5–20 — настраивать по cross-validation
- `class_weight="balanced"` обязательно — типично калибровочные точки распределены неравномерно по зонам

### 6. Метрология — по ISO/IEC 18305:2016

- **Detection Probability** для зон: доля правильно классифицированных позиций в каждой зоне (`workplace`, `corridor`, `meeting_room`, `outside_office`)
- **RMSE** (если работа с координатами): root-mean-square error дистанции между предсказанной и истинной позицией
- **Confusion Matrix**: обязательная визуализация в дипломе — какие зоны путаются с какими
- Оба классификатора (WKNN, RF) тестируются на ОДНОМ И ТОМ ЖЕ test-сете для корректного сравнения
- Test-сет должен быть **физически отделён** от калибровочного (другая сессия записи, не cross-validation внутри одного сбора)

## Рабочий процесс при реализации

### Шаг 1: Доменные модели (Pure Python, без зависимостей)

Положить в `backend/app/domain/radiomap/value_objects.py`:

```python
from dataclasses import dataclass
from datetime import datetime

MISSING_RSSI: int = -100

@dataclass(frozen=True)
class BSSID:
    """MAC-адрес точки доступа Wi-Fi (например, 'AA:BB:CC:DD:EE:FF')."""
    value: str

    def __post_init__(self) -> None:
        # Простая валидация формата
        if not _is_valid_mac(self.value):
            raise ValueError(f"Invalid BSSID format: {self.value}")

@dataclass(frozen=True)
class RSSIObservation:
    """RSSI от одной точки доступа в одном измерении."""
    bssid: BSSID
    rssi_dbm: int  # отрицательное значение в dBm

    def __post_init__(self) -> None:
        if not -120 <= self.rssi_dbm <= 0:
            raise ValueError(f"RSSI out of range: {self.rssi_dbm}")

@dataclass(frozen=True)
class RSSIVector:
    """Радиоотпечаток в одной точке: набор RSSI-измерений от видимых APs."""
    observations: tuple[RSSIObservation, ...]
    captured_at: datetime

    def to_dict(self) -> dict[str, int]:
        return {obs.bssid.value: obs.rssi_dbm for obs in self.observations}
```

### Шаг 2: Контракт классификатора (доменный Protocol)

`backend/app/domain/positioning/classifiers.py`:

```python
from typing import Protocol
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.radiomap.entities import Fingerprint
from app.domain.positioning.entities import ZoneClassification

class PositionClassifier(Protocol):
    """Контракт классификатора. Реализации: WKNN, RandomForest."""
    def classify(
        self,
        observation: RSSIVector,
        calibration_set: list[Fingerprint],
    ) -> ZoneClassification: ...
```

### Шаг 3: Реализация WKNN

См. шаблон [templates/wknn_classifier.py](templates/wknn_classifier.py).

Краткие правила:
- Извлечение признаков — отдельная функция (не внутри классификатора)
- Глобальный список BSSID кешируется при первом обучении
- `predict_proba` для уверенности классификации
- Логирование на DEBUG: размер калибровочного сета, число признаков, время обучения, время инференса

### Шаг 4: Реализация Random Forest

См. шаблон [templates/random_forest_classifier.py](templates/random_forest_classifier.py).

Тот же `PositionClassifier` Protocol, та же подача признаков. Разница только в самом классификаторе.

### Шаг 5: Метрология

См. шаблон [templates/metrology_evaluation.py](templates/metrology_evaluation.py).

Обязательные метрики для диссертации:
- Detection Probability per zone (table)
- Confusion matrix (heatmap)
- RMSE (если работаем с координатами; иначе — N/A)
- Время обучения и время инференса (для производственной целесообразности)

## Подробные ссылки

- [Методология фингерпринтинга и сравнение с альтернативами](references/METHODOLOGY.md)
- [Метрология ISO/IEC 18305:2016 — детальный гайд](references/METROLOGY.md)

## Шаблоны кода

- [WKNN-классификатор](templates/wknn_classifier.py) — реализует `PositionClassifier`
- [Random Forest классификатор](templates/random_forest_classifier.py) — реализует `PositionClassifier`
- [Извлечение признаков из RSSI](templates/feature_extractor.py) — `build_feature_matrix()` для калибровочного сета
- [Метрологическая оценка](templates/metrology_evaluation.py) — RMSE, Detection Probability, confusion matrix

## Anti-patterns (категорически избегать)

- ❌ **Преобразовывать RSSI в положительные числа.** Теряется физическая интерпретация и линейность по dB.
- ❌ **Использовать KNN без `weights="distance"`.** Это будет обычный KNN, а в дипломе заявлен WKNN.
- ❌ **Хардкодить `k=5` или `n_estimators=100` в коде модели.** Только через `infrastructure/ml/config.py` с возможностью переопределения в тестах.
- ❌ **Делать cross-validation внутри одного сбора и репортить как "точность системы".** Полевые испытания требуют физически отдельного test-сета.
- ❌ **Тренировать классификатор на каждом запросе классификации.** Тренировка — раз при загрузке/обновлении радиокарты, инференс — на каждом запросе.
- ❌ **Хранить ORM-модели в `domain/`.** SQLAlchemy импорт запрещён в `domain/`.
- ❌ **Передавать pandas DataFrame через границы слоёв.** Только Pydantic-схемы или dataclass-ы. Pandas — внутренний инструмент `infrastructure/ml/`.
- ❌ **Логировать полный RSSI-вектор на INFO.** Это PII (косвенно — позволяет реконструировать местоположение). Только на DEBUG.
- ❌ **Возвращать confidence < 0 или > 1 из `predict_proba`.** sklearn это валидирует, но own-классификаторы должны проверять.
