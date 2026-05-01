<!-- handoff:task:fe5c8e3e-29cf-4b73-8745-1c668f918c48 -->

# Implementation Plan: Приём радиоотпечатков и калибровка

Branch: feature/backend-fingerprints-calibration-fe5c8e
Created: 2026-05-01

## Settings

- Testing: yes (unit для value objects и use cases, integration для эндпоинтов)
- Logging: verbose (structlog с DEBUG)
- Docs: yes (mandatory checkpoint)

## Roadmap Linkage

Milestone: "Приём радиоотпечатков и калибровка"
Rationale: Шестая веха — данные radiomap'а, без которых ML-классификатор (следующая веха) не имеет ни обучающей выборки (калибровочные точки), ни входа (live-отпечатки от устройств). Mobile-приложение получает endpoint для отправки отпечатков; web-панель — endpoint для управления калибровочными точками.

## Цель плана

Реализовать REST API для приёма и хранения Wi-Fi RSSI-отпечатков двух видов:

**1. Live-отпечатки** (от устройства сотрудника во время работы):
- `POST /api/v1/fingerprints` — любой авторизованный сотрудник; `employee_id=current_user.id`, `is_calibration=False`, `zone_id=NULL` (классификация — следующая веха).
- `GET /api/v1/fingerprints` — admin; список с пагинацией и фильтрами (`employee_id`, `zone_id`, `from`/`to` по `captured_at`).
- `GET /api/v1/fingerprints/{id}` — admin для отладки.

**2. Калибровочные точки** (эталонные отпечатки admin-режима):
- `POST /api/v1/calibration/points` — admin-only; `is_calibration=True`, `zone_id` ОБЯЗАТЕЛЕН (CHECK calibration_requires_zone в БД).
- `GET /api/v1/calibration/points` — любой авторизованный (mobile/web нужен список для UI калибровки и визуализации radiomap'а).
- `DELETE /api/v1/calibration/points/{id}` — admin удаляет ошибочный эталон.

**Доменные value objects:**
- `BSSID` — MAC-адрес точки доступа в формате `AA:BB:CC:DD:EE:FF` (валидируется regex'ом и нормализуется в верхний регистр).
- `RSSIVector` — отображение `BSSID → dBm`; dBm валидируется в диапазоне `[-100, 0]` (физически реалистичный для Wi-Fi 2.4/5 GHz).
- `Fingerprint` уже есть как ORM, добавим domain-сущность.

После плана:
- Mobile может отправлять отпечатки → они попадают в БД.
- Admin может через web-панель управлять калибровочной радиокартой.
- ML-веха получит готовые `FingerprintRepository.list_calibrated_for_zone(...)` для обучения классификатора.

## Commit Plan

- **Commit 1** (Tasks 1-3): `chore(domain): radiomap — BSSID, RSSIVector, Fingerprint, FingerprintRepository`
- **Commit 2** (Task 4): `feat(infrastructure): SqlAlchemyFingerprintRepository`
- **Commit 3** (Tasks 5-9): `feat(radiomap): use cases приём отпечатков и управление калибровкой`
- **Commit 4** (Tasks 10-13): `feat(api): эндпоинты /fingerprints и /calibration/points + main wiring`
- **Commit 5** (Tasks 14-15): `test(unit): тесты value objects radiomap и use cases`
- **Commit 6** (Task 16): `test(integration): интеграционные тесты эндпоинтов radiomap`
- **Commit 7** (Task 17): `docs: руководство по приёму отпечатков и калибровке`

## Tasks

### Phase 1: Domain — value objects, entity, repository Protocol

- [x] **Task 1: `domain/radiomap/value_objects.py` — BSSID и RSSIVector**
  - **Deliverable:**
    - `BSSID` — frozen dataclass или класс с валидатором:
      - Формат: `^[0-9A-F]{2}(:[0-9A-F]{2}){5}$` (после нормализации)
      - Конструктор принимает строку любого регистра; нормализует в верхний (`AA:BB:CC:DD:EE:FF`)
      - Кидает `ValidationError(code="invalid_bssid", message="...")` если формат неверен
    - `RSSIVector` — frozen dataclass:
      - Поле `samples: dict[BSSID, int]` (immutable, кладём `MappingProxyType` или передаём frozenset of items)
      - Конструктор принимает `dict[str, int]` (или `dict[BSSID, int]`) и валидирует:
        - dBm в диапазоне `[-100, 0]` (валидно для Wi-Fi RSSI; за пределами — ValidationError с указанием BSSID и значения)
        - Минимум 1 точка доступа (пустой вектор бесполезен, ML не сможет классифицировать)
        - Максимум 200 точек (защита от DoS — реалистично десятки AP в офисе)
      - Метод `bssids() -> set[BSSID]` для быстрого пересечения с другими векторами
      - Метод `to_dict() -> dict[str, int]` для сохранения в JSONB (BSSID → строка)
  - **Файлы:** `backend/app/domain/radiomap/value_objects.py` (новый)
  - **LOGGING REQUIREMENTS:** N/A (pure value objects)
  - **Acceptance:** unit-тесты — невалидный MAC, dBm выше 0 / ниже -100, пустой вектор, нормализация регистра

- [x] **Task 2: `domain/radiomap/entities.py` — `Fingerprint` (domain)**
  - **Deliverable:** frozen dataclass `Fingerprint`:
    - `id: int` (0 для ещё-не-сохранённого)
    - `employee_id: int | None`
    - `zone_id: int | None`
    - `is_calibration: bool`
    - `captured_at: datetime` (timezone-aware UTC)
    - `device_id: str | None`
    - `rssi_vector: RSSIVector` (доменный value object, не dict)
    - `sample_count: int` (≥ 1)
  - Доменный инвариант: `is_calibration=True ⇒ zone_id is not None` (зеркалит DB CHECK calibration_requires_zone). Помещаем в `__post_init__` или классовый метод-фабрику.
  - **Файлы:** `backend/app/domain/radiomap/entities.py` (новый)
  - **LOGGING REQUIREMENTS:** N/A
  - **Acceptance:** unit — попытка создать `Fingerprint(is_calibration=True, zone_id=None, ...)` → ValidationError на доменном уровне

- [x] **Task 3: `domain/radiomap/repositories.py` — `FingerprintRepository` Protocol**
  - **Deliverable:**
    - `add(fingerprint: Fingerprint) -> Fingerprint` (с заполнением id)
    - `get_by_id(fingerprint_id: int) -> Fingerprint | None`
    - `list(*, employee_id: int | None = None, zone_id: int | None = None, is_calibration: bool | None = None, captured_from: datetime | None = None, captured_to: datetime | None = None, limit: int = 50, offset: int = 0) -> list[Fingerprint]`
    - `count(...) -> int` (те же фильтры)
    - `delete_by_id(fingerprint_id: int) -> bool` (для DELETE /calibration/points/{id})
    - **Bonus** (для ML на следующей вехе): `list_calibrated_for_zone(zone_id: int) -> list[Fingerprint]` — все калибровочные отпечатки конкретной зоны. Реализуем уже сейчас, чтобы ML-веха не редактировала Protocol.
  - **Файлы:** `backend/app/domain/radiomap/repositories.py` (новый)
  - **LOGGING REQUIREMENTS:** N/A (Protocol)
  - **Acceptance:** mypy strict проходит при использовании Protocol в use cases

### Phase 2: Infrastructure

- [x] **Task 4: `SqlAlchemyFingerprintRepository`**
  - **Deliverable:** `backend/app/infrastructure/repositories/fingerprints_repository.py`:
    - Реализует Protocol из Task 3.
    - `add` — преобразует `RSSIVector → dict` через `to_dict()` для сохранения в JSONB.
    - `_to_domain` — приватный маппер ORM → domain (включая сборку `RSSIVector` из JSONB).
    - При нарушении CHECK calibration_requires_zone (defense-in-depth, доменный инвариант ловится раньше) → `ValidationError(code="calibration_requires_zone")`.
    - Фильтры в `list/count` через `_apply_filters` (диапазон captured_at — `BETWEEN` или `>=` / `<=`).
  - **Файлы:** `backend/app/infrastructure/repositories/fingerprints_repository.py` (новый)
  - **LOGGING REQUIREMENTS:**
    - DEBUG на каждый метод с указанием филь́тров
    - INFO на add/delete с id и is_calibration
  - **Acceptance:** integration-тест с testcontainer — round-trip add → get_by_id → list с фильтрами

### Phase 3: Application — use cases

- [x] **Task 5: `SubmitFingerprintUseCase`** (live-замер от устройства)
  - **Deliverable:** `application/radiomap/submit_fingerprint.py`:
    - `SubmitFingerprintCommand(employee_id, captured_at, device_id, rssi_vector, sample_count)`
    - Алгоритм: создаёт `Fingerprint(is_calibration=False, zone_id=None)` и сохраняет.
    - **Антифрод**: проверка `captured_at` — нельзя «из будущего» (capture в > 5 минут вперёд от server now → ValidationError(code="captured_at_in_future")). Старые отпечатки (> 7 дней назад) тоже отбрасываем (ValidationError code="captured_at_too_old") — наверное mobile подключился после долгого офлайна, такие данные несвежие для классификации.
    - НЕ запускает классификацию (это веха ML).
  - **Файлы:** `backend/app/application/radiomap/__init__.py` (новый пустой), `submit_fingerprint.py` (новый)
  - **LOGGING REQUIREMENTS:**
    - INFO `[radiomap.submit.execute] success employee_id={id} fingerprint_id={fid} ap_count={n}`
    - WARN на отбракованные отпечатки с reason
  - **Acceptance:** unit с in-memory fake-repo — happy path; future captured_at → fail; too old → fail

- [x] **Task 6: `CreateCalibrationPointUseCase`** (admin)
  - **Deliverable:** `application/radiomap/calibrate_radiomap.py`:
    - `CreateCalibrationPointCommand(zone_id, captured_at, device_id, rssi_vector, sample_count, employee_id=None)`
    - Алгоритм: проверить, что zone_id существует (через ZoneRepository → если None → NotFoundError(zone_not_found)); создать `Fingerprint(is_calibration=True)`; сохранить.
    - Можно на старте делать `employee_id=None` — admin-калибровка не привязана к конкретному пользователю (просто факт замера).
  - **Файлы:** `backend/app/application/radiomap/calibrate_radiomap.py` (новый)
  - **LOGGING REQUIREMENTS:** INFO success / WARN на missing zone
  - **Acceptance:** unit — создание корректной точки; несуществующий zone_id → NotFoundError

- [x] **Task 7: `ListFingerprintsUseCase` + `GetFingerprintUseCase`** (admin)
  - **Deliverable:** `application/radiomap/list_fingerprints.py`:
    - `ListFingerprintsQuery(employee_id, zone_id, is_calibration, captured_from, captured_to, limit, offset)`
    - Возвращает `Page[Fingerprint]` (используем существующий `Page[T]` из `application/shared.py`).
    - `GetFingerprintQuery(fingerprint_id)` → `Fingerprint`; missing → NotFoundError.
  - **Файлы:** `backend/app/application/radiomap/list_fingerprints.py` (новый)
  - **LOGGING REQUIREMENTS:** DEBUG старт/конец с filters
  - **Acceptance:** unit — фильтрация работает корректно по всем измерениям

- [x] **Task 8: `ListCalibrationPointsUseCase`** (любой авторизованный)
  - **Deliverable:** `application/radiomap/list_calibration_points.py`:
    - `ListCalibrationPointsQuery(zone_id: int | None, limit, offset)` — внутри ставит `is_calibration=True`.
    - Возвращает `Page[Fingerprint]` (отпечатки, не отдельный CalibrationPoint — у нас одна сущность с is_calibration-флагом).
  - **Файлы:** `backend/app/application/radiomap/list_calibration_points.py` (новый)
  - **Acceptance:** unit — возвращает только калибровочные

- [x] **Task 9: `DeleteCalibrationPointUseCase`** (admin)
  - **Deliverable:** `application/radiomap/delete_calibration_point.py`:
    - `DeleteCalibrationPointCommand(fingerprint_id)`
    - Алгоритм: get_by_id → если None → NotFoundError; если `is_calibration=False` → ValidationError(code="not_a_calibration_point", message="Этот эндпоинт только для калибровочных отпечатков"); иначе delete_by_id.
    - Защищает от случайного удаления live-отпечатка через калибровочный endpoint.
  - **Файлы:** `backend/app/application/radiomap/delete_calibration_point.py` (новый)
  - **LOGGING REQUIREMENTS:** INFO success / WARN reason
  - **Acceptance:** unit — happy path; live-отпечаток → ValidationError; missing id → NotFoundError

### Phase 4: Presentation — schemas + endpoints + wiring

- [x] **Task 10: Pydantic-схемы radiomap**
  - **Deliverable:** `backend/app/presentation/schemas/radiomap.py`:
    - `FingerprintSubmitRequest`:
      - `captured_at: datetime` (timezone-aware required)
      - `device_id: str | None` (max 64)
      - `rssi_vector: dict[str, int]` (BSSID → dBm; ключи валидируются в use case через value object, но Pydantic делает быстрый sanity check `min_length=1`, `max_length=200`)
      - `sample_count: int = Field(default=1, ge=1, le=100)`
    - `CalibrationPointCreateRequest`: то же + обязательный `zone_id: int` (Field gt=0)
    - `FingerprintResponse(id, employee_id, zone_id, is_calibration, captured_at, device_id, rssi_vector, sample_count, created_at)` (created_at добавим из ORM)
    - `FingerprintsPageResponse(items, total, limit, offset)`
    - Все `extra="forbid"`
  - **Файлы:** `backend/app/presentation/schemas/radiomap.py` (новый)
  - **Acceptance:** Pydantic корректно отбрасывает rssi_vector с пустым dict, max_length валидируется

- [x] **Task 11: Endpoints `/api/v1/fingerprints`**
  - **Deliverable:** `backend/app/presentation/api/v1/fingerprints.py`:
    - `POST /` — Depends(get_current_user) → SubmitFingerprintUseCase → 201 + FingerprintResponse
    - `GET /` — Depends(require_role(Role.ADMIN)) → ListFingerprintsUseCase + query params (employee_id, zone_id, is_calibration, captured_from, captured_to, limit, offset)
    - `GET /{id}` — admin → GetFingerprintUseCase
    - Mapper `_to_response(Fingerprint) → FingerprintResponse` через `RSSIVector.to_dict()` для JSONB-словаря.
  - **Файлы:** `backend/app/presentation/api/v1/fingerprints.py` (новый)
  - **LOGGING REQUIREMENTS:** DEBUG start с employee_id (без rssi_vector целиком — может быть большим)
  - **Acceptance:** integration-тесты в Task 16

- [x] **Task 12: Endpoints `/api/v1/calibration/points`**
  - **Deliverable:** `backend/app/presentation/api/v1/calibration.py`:
    - `POST /` — admin → CreateCalibrationPointUseCase → 201
    - `GET /` — Depends(get_current_user) (любой авторизованный) → ListCalibrationPointsUseCase
    - `DELETE /{id}` — admin → DeleteCalibrationPointUseCase → 204
    - Префикс роутера: `/calibration` (не `/calibration-points`, чтобы потом добавить `/calibration/sessions` или другие endpoints для калибровки без нарушения структуры).
  - **Файлы:** `backend/app/presentation/api/v1/calibration.py` (новый)
  - **Acceptance:** integration-тесты

- [x] **Task 13: DI dependencies + main.py wiring**
  - **Deliverable:**
    - `presentation/dependencies.py`: `get_fingerprint_repository`, `get_submit_fingerprint_use_case`, `get_create_calibration_point_use_case`, `get_list_fingerprints_use_case`, `get_fingerprint_use_case`, `get_list_calibration_points_use_case`, `get_delete_calibration_point_use_case`
    - `main.py`: include `fingerprints_router` и `calibration_router`; обновить `[main.create_app] ready`
  - **Файлы:** `presentation/dependencies.py` (M), `main.py` (M)
  - **Acceptance:** Swagger показывает группы `fingerprints` и `calibration`

### Phase 5: Тесты

- [x] **Task 14: Unit-тесты domain value objects**
  - **Deliverable:** `tests/unit/domain/test_radiomap_value_objects.py`:
    - BSSID:
      - валидный MAC верхнего/нижнего регистра — нормализуется в верхний
      - инвалидный (`G0:00:...`, длиннее/короче) → ValidationError(invalid_bssid)
      - hashable, equal, разные значения != equal
    - RSSIVector:
      - валидный round-trip
      - dBm > 0 → ValidationError(rssi_out_of_range)
      - dBm < -100 → ValidationError(rssi_out_of_range)
      - empty samples → ValidationError(empty_rssi_vector)
      - 200+ AP → ValidationError(too_many_access_points)
      - `bssids()` возвращает множество BSSID
      - `to_dict()` round-trip с конструктором
    - Fingerprint:
      - is_calibration=True + zone_id=None → ValidationError(calibration_requires_zone)
  - **Файлы:** новый
  - **Acceptance:** ≥ 95% coverage на value_objects.py и entities.py

- [x] **Task 15: Unit-тесты use cases radiomap**
  - **Deliverable:** `tests/unit/application/test_submit_fingerprint.py`, `test_create_calibration_point.py`, `test_list_fingerprints.py`, `test_delete_calibration_point.py`:
    - In-memory `FakeFingerprintRepository` (расширим `tests/unit/application/fakes.py` или отдельный файл).
    - Покрытие: success, future captured_at, too old, missing zone, delete live-отпечатка через calibration endpoint, missing id.
  - **Файлы:** обновить `fakes.py` + 4 новых файла
  - **Acceptance:** ≥ 90% coverage application/radiomap/

- [x] **Task 16: Integration-тесты эндпоинтов radiomap**
  - **Deliverable:** `tests/integration/api/test_fingerprints.py` и `test_calibration.py`:
    - Fixtures: seeded admin/employee, seeded zone (одна с workplace, чтобы привязывать калибровочные точки).
    - Тесты:
      - `POST /fingerprints` employee → 201, проверить, что в БД сохранился с employee_id и is_calibration=False
      - `POST /fingerprints` без токена → 401
      - `POST /fingerprints` с captured_at в будущем → 400/422
      - `POST /fingerprints` с пустым rssi_vector → 422
      - `GET /fingerprints` admin → 200 + Page; employee → 403
      - `POST /calibration/points` admin → 201 с is_calibration=True
      - `POST /calibration/points` employee → 403
      - `POST /calibration/points` с несуществующим zone_id → 404
      - `GET /calibration/points` любой авторизованный → 200
      - `DELETE /calibration/points/{id}` admin успешно
      - `DELETE /calibration/points/{id}` non-admin → 403
      - `DELETE /calibration/points/{id}` для live-отпечатка (создан через POST /fingerprints) → 400 not_a_calibration_point
  - **Acceptance:** при наличии Docker все проходят

### Phase 6: Документация

- [x] **Task 17: Обновить `backend/README.md`**
  - **Deliverable:**
    - Раздел «Радиоотпечатки и калибровка» с описанием схемы (live vs калибровочные), curl-примерами для submit и create-calibration, описанием rssi_vector формата и ограничений
    - Таблица «Эндпоинты» — добавить новые пути
    - Раздел «Структура схемы БД» уже описывает `fingerprints` — обновить, если нужны новые инварианты
  - **Файлы:** `backend/README.md` (M)
  - **Acceptance:** примеры copy-pasteable

## Документационный чекпоинт (после Task 17)

- Раздел «Радиоотпечатки» в README с примерами submit/calibration/delete
- Описание формата RSSI-вектора и BSSID
- Открытые вопросы / ограничения (отсутствие классификации до ML-вехи)

## Открытые вопросы

- **Классификация и автоматическое создание AttendanceLog** — на следующей вехе (ML). Сейчас live-отпечаток просто сохраняется с `zone_id=None`.
- **Дедупликация / aggregation отпечатков** — пока каждый submit пишет отдельную запись. На вехе ML возможно введём агрегацию по окну (например, 1 минута) — будет отдельная задача.
- **Bulk submit** для mobile — пока 1 отпечаток за запрос. Если потребуется офлайн-кэш и пакетная отправка — добавим `POST /fingerprints/batch` отдельной задачей.
- **Аномальные RSSI** (например, все -100) — не отбраковываем; ML-веха решит, какие отбрасывать через гиперпараметры.
- **PII в логах**: rssi_vector содержит BSSID — это публичная инфраструктура (роутеры доступны всем рядом), не PII, безопасно. employee_id логируем — приемлемо для пилота.
- **Rate limiting на /fingerprints** — не делаем сейчас. Mobile-приложение может отправлять часто (несколько раз в минуту), но бесконечный поток с одного IP — anomaly. Добавим slowapi-лимит на этом эндпоинте, если на полевых испытаниях будут проблемы.
- **TimezoneAware captured_at** — обязательно (валидируется Pydantic). Mobile должен отправлять с timezone (UTC предпочтительно).
