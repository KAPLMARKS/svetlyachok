<!-- handoff:task:632a1b11-db23-4c0b-a463-2d1f379cb218 -->
# План: Backend MVP-доработки

**Ветка:** `feature/backend-mvp-tweaks-632a1b`
**Создан:** 2026-05-02
**Handoff task:** `632a1b11-db23-4c0b-a463-2d1f379cb218`

## Settings

- **Testing:** yes (unit + integration)
- **Logging:** verbose — `log.debug` на старт, `log.info` на ключевые переходы, `log.warning` на бизнес-исключения и rejected items
- **Docs:** yes — раздел в `backend/README.md` + обновление `docs/api.md` (или подраздел в `docs/`)

## Roadmap Linkage

- **Milestone:** "Backend MVP-доработки"
- **Rationale:** Реализует веху №9 ROADMAP.md — три критичных доработки (cache invalidation + bulk fingerprints + logout endpoint), без которых mobile/web вехи не заработают.

## Контекст и архитектурные решения

### 1. ML cache invalidation

**Проблема.** `_position_classifier_singleton` в `dependencies.py` обёрнут `@lru_cache(maxsize=1)`. После CRUD на `/api/v1/calibration/points` обученная модель не переобучается до рестарта backend — admin не видит эффекта калибровки на mobile.

**Решение.** Экспортировать публичную функцию `invalidate_position_classifier_cache()` в `dependencies.py`, которая вызывает `_position_classifier_singleton.cache_clear()`. Эта функция вызывается в эндпоинтах `POST /calibration/points` и `DELETE /calibration/points/{id}` после успешного `use_case.execute()`. Следующий `/classify` создаст новый `WknnClassifier` instance (через `is_trained() == False`) и lazy-обучит его на актуальных калибровочных данных.

**Почему cache_clear, а не reset() на классификаторе?** Singleton переключается на новый instance — гарантированно чистое состояние. `WknnClassifier` сейчас не имеет `reset()`-метода, и добавлять его не обязательно: cache_clear достигает того же результата минимальным изменением.

**Где вызывать?** В роутере (presentation), а не в use case — invalidation это инфраструктурная деталь композиции. Use case не должен знать про lru_cache.

**Безопасность.** invalidate-функция вызывается только в admin-only эндпоинтах (`require_role(Role.ADMIN)`). Гонок нет: lru_cache потокобезопасен, при следующем `_position_classifier_singleton()` создастся новый instance.

### 2. Bulk fingerprints

**Зачем.** Mobile (Flutter + WorkManager) копит отпечатки в sqflite-кэше при отсутствии сети, при появлении сети шлёт пачкой. На каждый отпечаток отдельный POST — N HTTP-запросов вместо одного, лишний пинг батареи и сети.

**Endpoint.** `POST /api/v1/fingerprints/batch`. Принимает массив до **100** отпечатков (компромисс: достаточно для типичного офлайн-периода ~30 мин при WorkManager-throttling Android 9+ ≤ 4 сканов/2 мин = ~60 за час, плюс запас).

**Семантика частичного успеха.** Каждый item обрабатывается через `SubmitFingerprintUseCase` независимо. Если один item падает (`ValidationError` про `captured_at_in_future` / `captured_at_too_old`), остальные сохраняются. Ответ:

```json
{
  "accepted": [
    {"index": 0, "fingerprint": {...полный FingerprintResponse...}},
    ...
  ],
  "rejected": [
    {"index": 3, "code": "captured_at_too_old", "message": "..."},
    ...
  ],
  "accepted_count": 7,
  "rejected_count": 1
}
```

Mobile удалит из sqflite только те записи, чей index в `accepted`. Остальные останутся для retry или логирования (либо удалятся как невалидные, если ошибка нерешаемая — например, captured_at старше 7 дней).

**HTTP status.** `200 OK` для смешанного ответа (даже если все items rejected — это бизнес-ответ, не транспортная ошибка). `400 Bad Request` только если запрос синтаксически невалиден (Pydantic-валидация массива/полей).

**Транзакционность.** Каждый item — отдельный `session.flush()` через repository.add. Если один item падает на DB-уровне (что не должно случаться, но defense-in-depth), он попадает в rejected, остальные сохраняются. Вместе с тем все items идут в одной FastAPI-транзакции (один `Depends(get_session)`); финальный commit делает FastAPI на выходе. Это компромисс между «всё или ничего» и «независимые сохранения» — для MVP подходит.

**Авторизация.** Same as POST /fingerprints — любой авторизованный сотрудник, `employee_id = current_user.id` подставляется автоматически (mobile не может подделать чужой employee_id).

### 3. Logout endpoint

**Минимальная реализация.** `POST /api/v1/auth/logout` принимает Bearer access-токен через стандартный `get_current_user` (валидирует подпись и срок), возвращает `200 {"message": "logged_out"}`. Сервер **не делает ничего** с самим токеном — клиент должен стереть свои локальные access + refresh.

**Почему так?** Полноценный logout с blacklist `jti` требует таблицу `revoked_tokens` + middleware-проверки на каждый запрос. Это отложено в «не в roadmap» (security hardening). Для MVP с короткоживущим access-токеном (30 минут) и одним пользователем на машине этого достаточно: украденный токен живёт максимум 30 минут.

**Зачем тогда endpoint вообще?** Web-панель должна иметь кнопку «Выйти» с серверным эндпоинтом для аудита (логируем `employee_id` сделавшего logout) и для будущей расширенной семантики (когда добавим blacklist — клиент уже шлёт правильный запрос). Также честный API-контракт: «logged out» — серверное событие, а не только клиентское.

**Rate limit.** Новая настройка `auth_logout_rate_limit` (default `10/minute`) — чтобы не позволить ddos через бесконечные logout-ы.

**Лог.** `log.info("[auth.logout] success", employee_id=...)`. Никаких security-warning'ов — обычная операция.

## Tasks

### Phase 1: ML cache invalidation

- [ ] **Task 1: Публичная функция invalidate**
  - **Файлы:** `backend/app/presentation/dependencies.py`
  - **Что:** Добавить публичную `def invalidate_position_classifier_cache() -> None`, которая вызывает `_position_classifier_singleton.cache_clear()`. Docstring с пояснением: вызывать после CRUD калибровочных точек, следующий /classify обучит модель на актуальных данных. Не помечать singleton'у — публичный API именно для invalidation.
  - **Логи:** `log.info("[dependencies.invalidate_position_classifier_cache] cleared")` — критично для отладки stale-моделей.

- [ ] **Task 2: Wiring в calibration-эндпоинты**
  - **Файлы:** `backend/app/presentation/api/v1/calibration.py`
  - **Что:**
    - В `create_calibration_point`: после успешного `await use_case.execute(cmd)` (но до `return`) вызвать `invalidate_position_classifier_cache()`.
    - В `delete_calibration_point`: то же самое.
    - Импорт через `from app.presentation.dependencies import invalidate_position_classifier_cache`.
  - **Логи:** уже есть в самой invalidate-функции; в эндпоинте — `log.debug("[calibration.endpoint.create] invalidating classifier cache")` перед вызовом.

- [ ] **Task 3: Integration-тесты cache invalidation**
  - **Файлы:** `backend/tests/integration/api/test_calibration_invalidation.py` (новый)
  - **Что:** Сценарий через httpx + testcontainers:
    1. Сидим 2 зоны × 5 калибровочных точек (центры -40, -80).
    2. `/classify` с RSSI у центра workplace → возвращает workplace.
    3. `DELETE /calibration/points/{id}` для всех точек workplace.
    4. `/classify` с тем же RSSI → должен либо вернуть corridor (другая ближайшая зона), либо 503 `insufficient_calibration_points` (если осталась только одна зона). Главное — **результат отличается от шага 2**, что доказывает retrain.
    5. Параллельный тест: `POST /calibration/points` с новой точкой outside-of-distribution → следующий `/classify` использует обновлённую выборку.
  - **Маркер:** `pytestmark = pytest.mark.integration`.

### Phase 2: Bulk fingerprints

- [ ] **Task 4: Pydantic-схемы bulk-запроса/ответа**
  - **Файлы:** `backend/app/presentation/schemas/radiomap.py` (расширить)
  - **Что:**
    - `FingerprintBulkSubmitRequest(BaseModel, extra=forbid)`: `items: list[FingerprintSubmitRequest] = Field(..., min_length=1, max_length=100)`. Limit 100 — оптимум, см. раздел контекста.
    - `BulkAcceptedItem`: `index: int`, `fingerprint: FingerprintResponse`.
    - `BulkRejectedItem`: `index: int`, `code: str`, `message: str`.
    - `FingerprintBulkSubmitResponse`: `accepted: list[BulkAcceptedItem]`, `rejected: list[BulkRejectedItem]`, `accepted_count: int`, `rejected_count: int`.
  - **Логи:** не требуются (схемы).

- [ ] **Task 5: SubmitFingerprintsBatchUseCase**
  - **Файлы:** `backend/app/application/radiomap/submit_fingerprints_batch.py` (новый)
  - **Что:**
    - `dataclass(frozen=True) SubmitFingerprintsBatchCommand`: `employee_id: int`, `items: list[SubmitFingerprintCommand]`. Команда уже существует — переиспользуем.
    - `dataclass(frozen=True) BatchAccepted`: `index: int`, `fingerprint: Fingerprint`.
    - `dataclass(frozen=True) BatchRejected`: `index: int`, `code: str`, `message: str`.
    - `dataclass(frozen=True) BatchResult`: `accepted: list[BatchAccepted]`, `rejected: list[BatchRejected]`.
    - `SubmitFingerprintsBatchUseCase` с зависимостью на `SubmitFingerprintUseCase` (композиция, не дублирование валидации).
    - Метод `execute(cmd) -> BatchResult`: цикл по items, вызывает `SubmitFingerprintUseCase.execute()`, ловит `AppError` (наследников: `ValidationError`, `ConflictError`), складывает в rejected. Любую неожиданную ошибку — пропустить наверх (5xx — баг сервера, а не невалидный item).
  - **Логи:** `log.debug("[fingerprints.batch.execute] start", employee_id, items_count)`. После цикла — `log.info("[fingerprints.batch.execute] done", accepted_count, rejected_count)`. Per-item rejection — `log.warning("[fingerprints.batch.execute] item_rejected", index, code, message)` (важно для отладки mobile-клиента).

- [ ] **Task 6: Endpoint + dependency wiring**
  - **Файлы:** `backend/app/presentation/api/v1/fingerprints.py`, `backend/app/presentation/dependencies.py`
  - **Что:**
    - В `dependencies.py`: добавить `get_submit_fingerprints_batch_use_case` (инжектит `SubmitFingerprintUseCase` через `get_submit_fingerprint_use_case` для композиции).
    - В `fingerprints.py`: новый POST `/batch` с `Depends(get_current_user)`, `Depends(get_submit_fingerprints_batch_use_case)`. Маппит `FingerprintBulkSubmitRequest.items[i]` → `SubmitFingerprintCommand` и собирает batch-команду. После execute — маппит `BatchResult` → `FingerprintBulkSubmitResponse`.
  - **Логи:** `log.debug("[fingerprints.endpoint.batch] start", employee_id, items_count)`. `log.info("[fingerprints.endpoint.batch] done", accepted_count, rejected_count)`.

- [ ] **Task 7: Тесты bulk fingerprints**
  - **Файлы:** `backend/tests/unit/application/test_submit_fingerprints_batch.py`, `backend/tests/integration/api/test_fingerprints_batch.py`
  - **Что:**
    - **Unit (5 тестов):** все приняты; один с `captured_at_in_future` → отклонён, остальные приняты; все отклонены (батч из невалидных); пустой items не пройдёт Pydantic-валидацию (отдельный тест на schema, не на use case); rejected содержит index в исходном массиве.
    - **Integration (3 теста):** успешный POST batch → 200 со всеми items в accepted; смешанный (1 валидный, 1 с captured_at_in_future) → 200 с accepted=[idx 0], rejected=[idx 1]; превышение max_length=100 → 422 от Pydantic.
  - **Маркеры:** `pytest.mark.unit` и `pytest.mark.integration`.

### Phase 3: Logout endpoint

- [ ] **Task 8: Settings + schema + endpoint + rate limit**
  - **Файлы:** `backend/app/core/config.py`, `backend/app/presentation/schemas/auth.py`, `backend/app/presentation/api/v1/auth.py`
  - **Что:**
    - В `config.py`: добавить `auth_logout_rate_limit: str = Field(default="10/minute", description="...")`.
    - В `auth.py` (schemas): `LogoutResponse(BaseModel, extra=forbid)`: `message: str = "logged_out"`. Однополевой, но соответствует паттерну Request/Response в проекте.
    - В `auth.py` (router): новый `@router.post("/logout", response_model=LogoutResponse, status_code=200)`. Декоратор `@limiter.limit(_settings.auth_logout_rate_limit)`. Параметр `request: Request` обязателен для slowapi. `current_user: Employee = Depends(get_current_user)`. Тело: `log.info("[auth.logout.endpoint] success", employee_id=current_user.id, role=current_user.role.value)` + `return LogoutResponse(message="logged_out")`.
    - **Никакого blacklist** — клиент сам стирает токены.
  - **Логи:** info на success (см. выше). Вместо warning на ошибки — стандартный 401 если токен невалиден придёт через `get_current_user` (UnauthorizedError → RFC 7807).

- [ ] **Task 9: Integration-тесты logout**
  - **Файлы:** `backend/tests/integration/api/test_auth.py` (расширить существующий)
  - **Что:** 3 теста:
    1. `POST /auth/logout` без токена → 401 `unauthorized`.
    2. `POST /auth/logout` с валидным токеном → 200 `{"message": "logged_out"}`.
    3. `POST /auth/logout` с тем же токеном повторно → 200 (токен ещё валиден до expiry; этот тест явно фиксирует — blacklist отложен).
  - **Маркер:** `pytest.mark.integration`.

### Phase 4: Документация

- [ ] **Task 10: README + docs обновления**
  - **Файлы:** `backend/README.md`, `docs/attendance.md` (если ссылки нужны), либо новый `docs/mvp-tweaks.md`
  - **Что:**
    - В `backend/README.md` (раздел «Эндпоинты»): добавить три строки:
      - `POST /api/v1/fingerprints/batch` — bulk-приём отпечатков
      - `POST /api/v1/auth/logout` — выход
      - Примечание: `POST /api/v1/calibration/points` и `DELETE /api/v1/calibration/points/{id}` теперь автоматически инвалидируют ML-кэш классификатора.
    - В разделе «Поведение lazy-обучения»: убрать ⚠️-примечание про «модель не инвалидируется автоматически — рестарт backend'а», заменить на «модель инвалидируется автоматически после CRUD на калибровочных точках».
    - В разделе «ML-классификация позиции» добавить подраздел про invalidation flow (одно предложение).
    - В «Учёт рабочего времени» — без изменений.
    - **Не создавать** docs/mvp-tweaks.md — это не отдельный feature-doc, а инкремент к существующим разделам.
  - **Язык:** русский.

## Commit Plan

10 задач — checkpoints через каждые 3 задачи:

- **Checkpoint 1 (после T3):** `feat(ml): автоматическая инвалидация singleton-классификатора после CRUD калибровки`
- **Checkpoint 2 (после T7):** `feat(api): POST /api/v1/fingerprints/batch — bulk-приём отпечатков`
- **Checkpoint 3 (после T9):** `feat(auth): POST /api/v1/auth/logout — минимальный logout endpoint`
- **Final commit (после T10):** `docs(backend): обновлены README и эндпоинты MVP-доработок`

## Принципы

1. Cache invalidation — в presentation-слое (роутер), не в application — это инфраструктурная деталь композиции.
2. Bulk fingerprints — partial success: один невалидный item не валит весь batch; все ошибки в rejected с index'ом.
3. Logout — минимально, без blacklist `jti` (явно отложено в «не в roadmap»). Клиент сам стирает токены.
4. Все timestamp'ы по-прежнему timezone-aware UTC.
5. Limit на batch-size (100) — через Pydantic `max_length` constraint.
6. Никаких magic-чисел: rate limit и batch size через Settings.
7. Тесты unit + integration, integration-тесты пропускаются без Docker (тоже политика проекта).
