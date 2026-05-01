<!-- handoff:task:a00682f7-4da8-423e-abae-d36c06d1989f -->

# Implementation Plan: ML-классификаторы (WKNN + Random Forest)

Branch: feature/backend-ml-classifiers-a00682
Created: 2026-05-01

## Settings

- Testing: yes (unit-тесты features.py, classifiers, metrics; метрологические тесты на синтетических данных)
- Logging: verbose (structlog DEBUG для отладки feature-извлечения и тренировки)
- Docs: yes (mandatory checkpoint)

## Roadmap Linkage

Milestone: "ML-классификаторы (WKNN + Random Forest)"
Rationale: Седьмая веха — ядро диплома. Реализует Protocol `PositionClassifier` через scikit-learn (WKNN с distance-weighting и Random Forest для baseline-сравнения), извлечение признаков из RSSI-векторов, конфиг гиперпараметров и метрологию по ISO/IEC 18305:2016 (Detection Probability, confusion matrix). Все последующие вехи (полевые испытания, метрологическая оценка, диссертация) опираются на эту реализацию.

## Цель плана

Реализовать классификацию позиции сотрудника по RSSI-вектору в одну из 4 зон (`workplace`, `corridor`, `meeting_room`, `outside_office`):

**Доменный Protocol**:
- `PositionClassifier` в `domain/positioning/classifiers.py` — единый контракт, который реализуют WKNN и Random Forest. ML-веха не нарушает Clean Architecture: domain не зависит от scikit-learn.

**Две реализации** (по плану диплома — сравниваем):
- `WknnClassifier` — `KNeighborsClassifier(weights="distance")` из scikit-learn
- `RandomForestClassifier` — `sklearn.ensemble.RandomForestClassifier`

**Феча-инжиниринг**:
- Стабильный список BSSID, фиксируемый при тренировке (хранится в model state)
- Преобразование разреженного `RSSIVector` в плотный feature-вектор по фиксированному списку BSSID
- Отсутствующий BSSID → `MISSING_RSSI = -100` (noise floor)

**Метрики (ISO/IEC 18305:2016)**:
- Detection Probability per-zone и overall (доля корректных классификаций)
- Confusion matrix (для визуализации в дипломе)

**API endpoint**:
- `POST /api/v1/positioning/classify` (любой авторизованный) — принимает RSSI-вектор → возвращает `ZoneClassification(zone_id, zone_type, confidence)`

**Конфигурация**:
- `infrastructure/ml/config.py` — все гиперпараметры (k, weights, metric, n_estimators, max_depth, random_state) хранятся как dataclass'ы. Версионируется в git для воспроизводимости экспериментов.

**Воспроизводимость**:
- Random seeds зафиксированы (`random_state=42`)
- Класс `class_weight="balanced"` для RF — защита от несбалансированных калибровочных данных
- Минимум калибровочных точек проверяется до тренировки (KNN требует хотя бы k точек)

После плана:
- `curl -X POST /api/v1/positioning/classify -d '{"rssi_vector": {...}}'` → `{"zone_id": 42, "zone_type": "workplace", "confidence": 0.87, "classifier": "wknn"}`
- Метрологические тесты `pytest tests/ml/` показывают Detection Probability ≥ 0.7 на синтетическом радиокарте (на реальных данных будет лучше после полевых испытаний)
- Диссертационный отчёт получит готовое сравнение WKNN vs Random Forest на одном test set'е

## Commit Plan

- **Commit 1** (Tasks 1-2): `chore(domain): scikit-learn + numpy в зависимости, domain positioning entities и Protocol`
- **Commit 2** (Tasks 3-4): `feat(ml): config с гиперпараметрами и features.py для извлечения признаков`
- **Commit 3** (Tasks 5-6): `feat(ml): WKNN и Random Forest классификаторы`
- **Commit 4** (Task 7): `feat(ml): метрики ISO/IEC 18305 (Detection Probability, confusion matrix)`
- **Commit 5** (Tasks 8-10): `feat(positioning): use cases классификации позиции`
- **Commit 6** (Tasks 11-13): `feat(api): эндпоинт POST /positioning/classify + main wiring`
- **Commit 7** (Tasks 14-16): `test(unit): тесты features, classifiers и metrics`
- **Commit 8** (Tasks 17-18): `test(integration + ml): /classify endpoint + метрологические тесты`
- **Commit 9** (Task 19): `docs: руководство по ML-классификации позиции`

## Tasks

### Phase 1: Зависимости и domain

- [x] **Task 1: Добавить scikit-learn и numpy в `pyproject.toml`**
  - **Deliverable:**
    - Production deps: `scikit-learn>=1.5.0,<2.0.0`, `numpy>=2.0.0,<3.0.0`
    - **Pin** для воспроизводимости — в комментарии указать, что апгрейд `scikit-learn` требует rerun метрологических тестов и фиксации новых эталонных метрик
  - **Файлы:** `backend/pyproject.toml` (M)
  - **Acceptance:** `pip install -e .[dev]` отрабатывает; `python -c "import sklearn, numpy; print(sklearn.__version__)"` ок

- [x] **Task 2: Domain — entities и Protocol для positioning**
  - **Deliverable:**
    - `app/domain/positioning/__init__.py` (новый пустой)
    - `app/domain/positioning/value_objects.py`:
      - `Confidence` frozen dataclass с `value: float` (валидация `0.0 <= value <= 1.0`)
    - `app/domain/positioning/entities.py`:
      - `ZoneClassification` frozen dataclass: `zone_id: int`, `zone_type: ZoneType`, `confidence: Confidence`, `classifier_name: str` (для логирования и диагностики)
    - `app/domain/positioning/classifiers.py`:
      - Protocol `PositionClassifier`:
        - `train(self, calibration_set: list[Fingerprint]) -> None` — обучение/refit
        - `classify(self, observation: RSSIVector) -> ZoneClassification` — предсказание
        - `is_trained() -> bool` — узнать, готов ли классификатор
      - `class TrainingError(Exception)` для диагностики (например, «недостаточно калибровочных точек»)
  - **Файлы:** новые файлы выше
  - **LOGGING REQUIREMENTS:** N/A (Protocol)
  - **Acceptance:** `from app.domain.positioning.classifiers import PositionClassifier` без побочных импортов scikit-learn

### Phase 2: ML инфраструктура

- [x] **Task 3: `infrastructure/ml/config.py` — гиперпараметры**
  - **Deliverable:**
    - `WknnConfig` frozen dataclass: `n_neighbors: int = 3`, `weights: Literal["distance"] = "distance"` (наш WKNN), `metric: Literal["euclidean", "cityblock", "chebyshev"] = "euclidean"`
    - `RandomForestConfig` frozen dataclass: `n_estimators: int = 100`, `max_depth: int | None = None`, `min_samples_split: int = 2`, `class_weight: Literal["balanced"] = "balanced"`, `random_state: int = 42`
    - `MISSING_RSSI: int = -100` (константа модуля — используется в features.py)
    - `MIN_CALIBRATION_POINTS_PER_ZONE: int = 3` (минимум для KNN с k=3)
    - В docstring модуля — пояснение, что апгрейд гиперпараметров инвалидирует все ранее обученные модели и требует rerun метрологических тестов
  - **Файлы:** `backend/app/infrastructure/ml/__init__.py` (M, экспорт), `backend/app/infrastructure/ml/config.py` (новый)
  - **Acceptance:** unit-тест: WknnConfig() и RandomForestConfig() instantiate без аргументов; mypy strict проходит

- [x] **Task 4: `infrastructure/ml/features.py` — извлечение признаков**
  - **Deliverable:**
    - `build_feature_matrix(calibration_set: list[Fingerprint]) -> tuple[np.ndarray, np.ndarray, list[BSSID]]`:
      - Возвращает `(X, y, bssid_index)` где `X` — `[N, M]` row-major numpy array (N — число калибровочных точек, M — общее число уникальных BSSID), `y` — массив `[N]` zone_id, `bssid_index` — упорядоченный список BSSID (стабильный порядок для воспроизводимости)
      - Отсутствующий BSSID в конкретном fingerprint заполняется `MISSING_RSSI` (noise floor)
      - Если `calibration_set` пуст или какая-то зона имеет < `MIN_CALIBRATION_POINTS_PER_ZONE` точек — `TrainingError(message=...)`
      - BSSID-список сортируется лексикографически (для стабильности между перезапусками)
    - `build_observation_vector(observation: RSSIVector, bssid_index: list[BSSID]) -> np.ndarray`:
      - Возвращает `[1, M]` numpy array: значения по `bssid_index`; отсутствующий BSSID → `MISSING_RSSI`
      - **Важно**: новые BSSID, которых не было в калибровочном наборе, ИГНОРИРУЮТСЯ (не добавляются в feature) — иначе нарушится контракт «модель обучена на M фичах»
    - Логирование: DEBUG старт с count fingerprints / уникальных BSSID; INFO готовности с размерами матрицы
  - **Файлы:** `backend/app/infrastructure/ml/features.py` (новый)
  - **Acceptance:** unit-тесты на разные сценарии (overlap BSSID, новый BSSID в observation, sparse vector → noise floor)

- [x] **Task 5: `infrastructure/ml/wknn_classifier.py` — WKNN реализация**
  - **Deliverable:**
    - `WknnClassifier(PositionClassifier)`:
      - `__init__(self, config: WknnConfig)` — сохраняет config; модель не обучается до train()
      - `_clf: KNeighborsClassifier | None = None`, `_bssid_index: list[BSSID] | None = None`, `_zone_types: dict[int, ZoneType] | None = None` (mapping zone_id → ZoneType, заполняется при train для возврата zone_type в ZoneClassification)
      - `train(calibration_set)`:
        1. `build_feature_matrix(calibration_set)` → X, y, bssid_index
        2. Сохранить bssid_index, zone_types
        3. Создать `KNeighborsClassifier(n_neighbors=config.n_neighbors, weights=config.weights, metric=config.metric)`
        4. `.fit(X, y)`
        5. Залогировать INFO `[ml.wknn.train] done` с размерами и параметрами
      - `classify(observation: RSSIVector) -> ZoneClassification`:
        1. Если `not is_trained()` → `TrainingError(code="not_trained")`
        2. `vec = build_observation_vector(observation, self._bssid_index)`
        3. `predicted = self._clf.predict(vec)[0]` — zone_id
        4. `proba = self._clf.predict_proba(vec)[0]` — вероятности; `confidence = max(proba)`
        5. Вернуть `ZoneClassification(zone_id=int(predicted), zone_type=self._zone_types[predicted], confidence=Confidence(float(confidence)), classifier_name="wknn")`
      - `is_trained() -> bool`: проверка `self._clf is not None`
  - **Файлы:** `backend/app/infrastructure/ml/wknn_classifier.py` (новый)
  - **LOGGING REQUIREMENTS:**
    - INFO на train: размер набора, n_zones, n_bssids
    - DEBUG на classify: predicted_zone, confidence
  - **Acceptance:** unit-тест на синтетических данных — линейно разделимые зоны → 100% accuracy

- [x] **Task 6: `infrastructure/ml/random_forest_classifier.py` — RF реализация**
  - **Deliverable:** аналогично WKNN, но через `sklearn.ensemble.RandomForestClassifier(n_estimators=config.n_estimators, max_depth=config.max_depth, min_samples_split=config.min_samples_split, class_weight=config.class_weight, random_state=config.random_state)`. `classifier_name="random_forest"`.
  - **Файлы:** `backend/app/infrastructure/ml/random_forest_classifier.py` (новый)
  - **Acceptance:** unit-тест на синтетических данных; результаты воспроизводимы между запусками (благодаря random_state)

- [x] **Task 7: `infrastructure/ml/metrics.py` — метрики ISO/IEC 18305**
  - **Deliverable:**
    - `@dataclass(frozen=True) class ClassificationMetrics`: `total_samples: int`, `correct: int`, `detection_probability: float` (overall, в [0, 1]), `per_zone_detection_probability: dict[int, float]`, `confusion_matrix: dict[tuple[int, int], int]` (предсказанная_zone_id, истинная_zone_id) → count.
    - `evaluate_classifier(classifier: PositionClassifier, test_set: list[tuple[RSSIVector, int]]) -> ClassificationMetrics`:
      - Прогон каждой пары (RSSIVector, true_zone_id) через `classifier.classify`
      - Подсчёт overall и per-zone Detection Probability
      - Сборка confusion matrix
    - `format_confusion_matrix(metrics: ClassificationMetrics, zone_names: dict[int, str]) -> str` — table-вид для логов и отчётов
  - **Файлы:** `backend/app/infrastructure/ml/metrics.py` (новый)
  - **Acceptance:** unit-тест на известной confusion matrix → корректные DP

### Phase 3: Application

- [x] **Task 8: Расширить `FingerprintRepository` — `list_calibrated_all()`**
  - **Deliverable:**
    - В `domain/radiomap/repositories.py` добавить метод `list_calibrated_all() -> List[Fingerprint]` — все калибровочные точки (для обучения классификатора на всём наборе)
    - Реализовать в `infrastructure/repositories/fingerprints_repository.py`: `select(...).where(is_calibration=True).order_by(captured_at)`
    - Расширить `tests/unit/application/fakes.py: FakeFingerprintRepository` соответствующим методом
  - **Файлы:** `repositories.py` (M), `fingerprints_repository.py` (M), `fakes.py` (M)
  - **Acceptance:** unit-тест fake-репо корректно возвращает только калибровочные

- [x] **Task 9: `ClassifyLocationUseCase`**
  - **Deliverable:**
    - `app/application/positioning/__init__.py` (новый пустой)
    - `app/application/positioning/classify_location.py`:
      - `ClassifyLocationCommand(rssi_vector: RSSIVector)` (employee_id опционально, для будущей привязки к AttendanceLog)
      - `class ClassifyLocationUseCase`:
        - `__init__(self, fingerprint_repo: FingerprintRepository, classifier: PositionClassifier)`
        - `async def execute(cmd) -> ZoneClassification`:
          1. Если `not classifier.is_trained()` → загрузить калибровочный набор через `fingerprint_repo.list_calibrated_all()` и сделать `classifier.train(set)`. Если `TrainingError` — пробросить (это ошибка конфигурации/калибровки, не пользовательская).
          2. `classifier.classify(cmd.rssi_vector)` → `ZoneClassification`
          3. Залогировать INFO с predicted_zone и confidence
      - **Кеширование модели**: lazy — модель тренируется при первом запросе; при добавлении/удалении калибровочной точки её надо инвалидировать. Для простоты на этой вехе — модель тренируется при каждом запросе (на 50-100 калибровочных точек это < 50 ms). Если будет тормозить — добавим кеш через WeakRef или явный invalidate-flag.
  - **Файлы:** новый
  - **LOGGING REQUIREMENTS:**
    - INFO `[positioning.classify.execute] success classifier={name} zone_id={id} confidence={c}`
    - WARN на TrainingError с reason
  - **Acceptance:** unit-тест с in-memory FakeFingerprintRepository заполненным калибровочными точками + WknnClassifier → ZoneClassification с разумным confidence

- [x] **Task 10: Опциональный `TrainClassifierUseCase`**
  - **Deliverable:**
    - `app/application/positioning/train_classifier.py`:
      - `TrainClassifierUseCase` — explicit entry point для админа форсировать переобучение (если будет admin endpoint в будущем)
      - На пилоте используется внутри `ClassifyLocationUseCase`; отдельный use case упрощает добавление endpoint'а позже
  - **Файлы:** новый
  - **Acceptance:** unit-тест успешного train на достаточной выборке; TrainingError на пустой/малой

### Phase 4: Presentation

- [x] **Task 11: Pydantic-схемы positioning**
  - **Deliverable:** `backend/app/presentation/schemas/positioning.py`:
    - `ClassifyRequest`: `rssi_vector: dict[str, int]` (Annotated с min_length=1, max_length=200, как в /fingerprints)
    - `ClassifyResponse`: `zone_id: int`, `zone_type: str`, `confidence: float`, `classifier_name: str`
    - Все `extra="forbid"`
  - **Файлы:** новый
  - **Acceptance:** Pydantic round-trip ок

- [x] **Task 12: Endpoint `POST /api/v1/positioning/classify`**
  - **Deliverable:** `backend/app/presentation/api/v1/positioning.py`:
    - `POST /classify` — `Depends(get_current_user)` (любой авторизованный), use_case = ClassifyLocationUseCase, преобразование payload.rssi_vector → RSSIVector value object, обработка TrainingError → 503 Service Unavailable + `code="classifier_not_ready"` (нет калибровочных данных)
  - **Файлы:** `backend/app/presentation/api/v1/positioning.py` (новый)
  - **Acceptance:** integration-тесты в Task 17

- [x] **Task 13: DI dependencies + main.py wiring**
  - **Deliverable:**
    - `presentation/dependencies.py`: `get_position_classifier() -> PositionClassifier` — singleton WknnClassifier с `lru_cache(1)` (для пилота используем WKNN; если решим переключиться на RF — поменяем здесь). `get_classify_location_use_case`.
    - `main.py`: include `positioning_router`; обновить лог.
    - **Замечание**: TrainingError должна обрабатываться в exception_handlers — добавим mapping → 503 с RFC 7807. Если TrainingError наследник AppError — обработка через существующий handler.
  - **Файлы:** `dependencies.py` (M), `main.py` (M), возможно `domain/shared/exceptions.py` (M — добавить `ServiceUnavailableError(AppError)` со status_code=503)
  - **Acceptance:** Swagger показывает группу `positioning`; uvicorn стартует

### Phase 5: Тесты

- [x] **Task 14: Unit-тесты `features.py`**
  - **Deliverable:** `tests/unit/infrastructure/ml/__init__.py`, `test_features.py`:
    - `test_build_feature_matrix_basic` — три fingerprint'а с overlap BSSID → корректная матрица, sorted bssid_index
    - `test_missing_bssid_filled_with_noise_floor` — sparse fingerprints, отсутствующие BSSID = -100
    - `test_observation_with_unknown_bssid_ignored` — новый BSSID в observation не нарушает feature size
    - `test_empty_calibration_raises_training_error` — нет данных
    - `test_too_few_points_per_zone_raises` — одна зона < MIN_CALIBRATION_POINTS_PER_ZONE
    - `test_bssid_index_stable_across_calls` — повторный вызов с теми же данными даёт тот же порядок BSSID
  - **Файлы:** новые
  - **Acceptance:** ≥ 90% coverage features.py

- [x] **Task 15: Unit-тесты classifiers**
  - **Deliverable:** `tests/unit/infrastructure/ml/test_classifiers.py`:
    - Synthetic dataset: 4 зоны × 5 точек, классы линейно разделимы по 2 BSSID
    - WKNN train+classify → 100% accuracy на самих training data; observation внутри cluster предсказывается правильно
    - RF train+classify аналогично; результат воспроизводим (`random_state=42`)
    - is_trained() работает корректно
    - classify до train → TrainingError(not_trained)
    - train на пустом наборе → TrainingError
  - **Файлы:** новый
  - **Acceptance:** все тесты проходят за < 5 секунд

- [x] **Task 16: Unit-тесты `metrics.py`**
  - **Deliverable:** `tests/unit/infrastructure/ml/test_metrics.py`:
    - Известная confusion matrix → правильный overall DP и per-zone DP
    - Все правильные → DP=1.0
    - Все неправильные → DP=0.0
    - Несбалансированный test set → per-zone DP корректно учитывает пропорции
  - **Файлы:** новый
  - **Acceptance:** покрытие metrics.py 100%

- [x] **Task 17: Integration-тест `/classify` endpoint**
  - **Deliverable:** `tests/integration/api/test_positioning.py`:
    - Fixtures: seeded zone + 3+ калибровочных fingerprint'а на эту зону через прямой db_engine commit (нужен реальный полноценный набор для тренировки)
    - `POST /classify` без токена → 401
    - `POST /classify` с пустым rssi_vector → 422
    - `POST /classify` с правильным rssi_vector (близким к калибровочному) → 200 + ZoneClassification с предсказанным zone_id и confidence > 0
    - `POST /classify` без калибровочных данных в БД → 503 `classifier_not_ready` (или какой-то осмысленный error)
  - **Файлы:** новый
  - **Acceptance:** integration-тесты проходят при наличии Docker

- [x] **Task 18: Метрологические тесты `tests/ml/`**
  - **Deliverable:** `tests/ml/test_wknn_metrics.py` и `test_random_forest_metrics.py`:
    - Синтетический dataset: 4 зоны × 10 калибровочных точек × 5 BSSID, физически разделимый (центры зон различаются по RSSI на 20+ dBm).
    - Тестовый сет: те же 4 зоны × 5 новых точек, расположенных рядом с центрами зон с шумом ±5 dBm
    - **Acceptance**: WKNN и RF на этом dataset должны давать `Detection Probability >= 0.7` (на реальных данных будет лучше)
    - Сравнение классификаторов на ОДНОМ test set'е через `evaluate_classifier`; результат сохраняется в JSON-артефакт (опционально, не обязательно для тестов)
    - Confusion matrix логируется через `format_confusion_matrix` для отладки
  - **Файлы:** `tests/ml/__init__.py` (если ещё нет), `tests/ml/test_wknn_metrics.py`, `tests/ml/test_random_forest_metrics.py`
  - **Acceptance:** оба теста зелёные с фиксированным seed

### Phase 6: Документация

- [x] **Task 19: Обновить `backend/README.md`**
  - **Deliverable:**
    - Раздел «ML-классификация позиции» с:
      - Описанием схемы (RSSI-вектор → KNeighbors / RandomForest → ZoneClassification)
      - Примером curl `POST /api/v1/positioning/classify`
      - Описанием конфигурации (`infrastructure/ml/config.py`)
      - Описанием метрик ISO/IEC 18305
      - Минимальным требованием к калибровочным данным (`MIN_CALIBRATION_POINTS_PER_ZONE`)
    - Таблица «Эндпоинты» — добавить `/positioning/classify`
  - **Файлы:** `backend/README.md` (M)
  - **Acceptance:** разделы читаются без перехода в исходники; примеры copy-pasteable

## Документационный чекпоинт (после Task 19)

- Раздел «ML-классификация позиции» в README с примерами и описанием
- Описание гиперпараметров и их влияния на метрики
- Минимальное требование к калибровочной выборке

## Открытые вопросы

- **Кеширование обученной модели**: пока тренируем на каждый запрос. Если на пилоте 50+ калибровочных точек × < 50 ms → ОК. На полевых испытаниях с 200+ точками может потребоваться кеш. Решение: добавить module-level cache + invalidate на CRUD calibration. Отдельная задача.
- **Persistence обученной модели** (pickle/joblib) — не делаем; на пилоте retrain дешевле serializa. На production-готовности добавим.
- **Ensemble (WKNN + RF voting)** — не делаем для пилота; это улучшение для production.
- **Feature engineering**: пока берём raw RSSI как features. Можно добавить:
  - Нормализацию (z-score per BSSID) — обычно не нужно для KNN с euclidean
  - Полиномиальные features (взаимодействия BSSID × BSSID) — может улучшить RF, но усложнит интерпретацию
  - Pearson correlation features — отдельная задача после полевых испытаний
- **Online learning** (обновление модели без полного refit) — не реализуем. Sklearn KNN не поддерживает partial_fit; RF поддерживает через `warm_start`, но добавляет complexity. Полный refit на 200 точках занимает миллисекунды.
- **Hyperparameter tuning** через `GridSearchCV` или `Optuna` — не делаем сейчас. После полевых испытаний — отдельная задача в рамках вехи «Метрологическая оценка».
- **Confidence threshold**: не отказываемся от классификации при низком confidence. Если потребуется — добавим параметр `min_confidence` в config; ниже → возвращаем `outside_office` или `unknown`.
- **Per-zone classifier** (по одной модели на зону) — не делаем; multiclass single-classifier — стандарт для indoor positioning.
