<!-- handoff:task:a790eae4-2880-4c9d-a6e2-8850bdb91453 -->
# План: Учёт рабочего времени

**Ветка:** `feature/backend-attendance-tracking-a790ea`
**Создан:** 2026-05-02
**Handoff task:** `a790eae4-2880-4c9d-a6e2-8850bdb91453`

## Settings

- **Testing:** yes (unit + integration, тесты в плане)
- **Logging:** verbose — `log.debug` на старт, `log.info` на ключевые переходы, `log.warning` на бизнес-исключения
- **Docs:** yes — `backend/README.md` обновляется, добавляется `docs/attendance.md` с описанием API и логики сессий

## Roadmap Linkage

- **Milestone:** "Учёт рабочего времени"
- **Rationale:** План реализует веху №8 ROADMAP.md — AttendanceLog авто-создаётся при `/classify`, REST API учёта посещаемости, расчёт `work_hours`. БЕЗ интеграции с 1С/ERP.

## Контекст и архитектурные решения

### Что уже есть

- `AttendanceLog` ORM в `backend/app/infrastructure/db/orm/attendance.py` — поля `id`, `employee_id`, `zone_id`, `started_at`, `ended_at`, `duration_seconds`, `status` (enum: present/late/absent/overtime), partial index `ix_attendance_logs_open_sessions WHERE ended_at IS NULL`, CHECK-constraints `ended_after_started` и `duration_non_negative`.
- `Employee.schedule_start/end` (`time | None`) — уже в домене и ORM.
- `POST /api/v1/positioning/classify` возвращает `ClassifyResponse(zone_id, zone_type, confidence, classifier_name)` и имеет доступ к `current_user.id`.

### Чего не хватает

- Поле `last_seen_at` (timestamptz, nullable) в `attendance_logs` — для inactivity timeout. Сессия продлевается через UPDATE этого поля при каждом classify в той же зоне; при срабатывании таймаута `ended_at = last_seen_at`.
- Domain layer `app/domain/attendance/` (пустой `__init__.py`) — нужно создать с нуля.
- Application layer `app/application/attendance/` — use cases.
- SqlAlchemy-репозиторий и схемы.
- Wiring в `dependencies.py` + интеграция с classify-эндпоинтом.

### Логика сессий (RecordAttendanceUseCase)

При каждом успешном `/classify(employee_id=E, predicted_zone=Z, now=T)`:

1. Найти открытую сессию для `E` (`ended_at IS NULL`).
2. **Нет открытой** → создать новую: `started_at=T, last_seen_at=T, zone_id=Z, status=compute_status(T, Z, employee.schedule_start)`.
3. **Есть открытая, та же зона, `T - last_seen_at <= INACTIVITY_TIMEOUT`** → продлить: `last_seen_at=T`.
4. **Есть открытая, та же зона, `T - last_seen_at > INACTIVITY_TIMEOUT`** → закрыть с `ended_at=last_seen_at`, открыть новую с `started_at=T`.
5. **Есть открытая, другая зона** → закрыть с `ended_at=T`, открыть новую с `started_at=T, zone_id=Z`.

При закрытии — пересчёт `duration_seconds = (ended_at - started_at).total_seconds()` и финальный `status` (включая `overtime` если `ended_at > schedule_end`).

`INACTIVITY_TIMEOUT` — конфигурируется через env (`ATTENDANCE_INACTIVITY_TIMEOUT_SECONDS`, default `1800` = 30 минут).

### Расчёт статуса

- `present` — зона `workplace`, `started_at` в пределах `[schedule_start, schedule_end]` (если у сотрудника задан график).
- `late` — зона `workplace`, `started_at.time() > schedule_start`.
- `overtime` — `ended_at.time() > schedule_end` (определяется при закрытии).
- `absent` — резервный (используется только в агрегациях, в open/close логике не появляется).
- Если у сотрудника нет графика (`schedule_start IS NULL`) — `present` для рабочих зон, без late/overtime.

### REST API

- `GET /api/v1/attendance` — список сессий с фильтрами (`employee_id`, `started_from`, `started_to`, `zone_id`, `status`, `limit`, `offset`). Доступ: admin (любой сотрудник), employee (только свои логи).
- `GET /api/v1/attendance/summary` — агрегация по периоду (`employee_id`, `from`, `to`): `work_hours_total` (часы в `workplace`), `lateness_count`, `overtime_seconds_total`, `sessions_count`. Доступ: admin (любой), employee (свой).

## Tasks

### Phase 1: Domain layer

- [x] **Task 1: Доменные value objects и enum**
  - **Файлы:** `backend/app/domain/attendance/value_objects.py`
  - **Что:** Создать enum `AttendanceStatus` (значения: `present`, `late`, `absent`, `overtime` — синхронно с ORM-enum). Создать `dataclass(frozen=True) WorkInterval` (start: datetime, end: datetime | None, продолжительность через property `duration: timedelta | None`).
  - **Логи:** не требуются (чистые VO)
  - **Граница:** только stdlib + pydantic. Никаких импортов sqlalchemy/fastapi.

- [x] **Task 2: Доменная сущность AttendanceLog**
  - **Файлы:** `backend/app/domain/attendance/entities.py`
  - **Что:** `dataclass(frozen=True) AttendanceLog` с полями: `id: int`, `employee_id: int`, `zone_id: int`, `started_at: datetime`, `ended_at: datetime | None`, `last_seen_at: datetime`, `duration_seconds: int | None`, `status: AttendanceStatus`. В `__post_init__` валидировать timezone-awareness (`started_at.tzinfo is not None` иначе `ValidationError("attendance_naive_datetime")`), `ended_at IS NULL OR ended_at > started_at`, `duration_seconds >= 0 OR is None`.
  - **Property:** `is_open: bool` (`ended_at is None`).
  - **Логи:** не требуются (entity).

- [x] **Task 3: Доменный сервис расчёта статуса**
  - **Файлы:** `backend/app/domain/attendance/services.py`
  - **Что:** Функция `compute_status_on_open(started_at: datetime, zone_type: ZoneType, schedule_start: time | None) -> AttendanceStatus` — возвращает `late`/`present`. Функция `compute_final_status(started_at, ended_at, current_status, schedule_end) -> AttendanceStatus` — повышает до `overtime` если `ended_at.time() > schedule_end`.
  - **Логи:** `log.debug("[attendance.compute_status] ...", started_at, schedule_start, result)` для отладки граничных случаев.
  - **Зависимости:** Импортирует `ZoneType` из `app/domain/zones/value_objects.py` (или где он определён — выяснить при имплементации).

- [x] **Task 4: Доменный repository Protocol**
  - **Файлы:** `backend/app/domain/attendance/repositories.py`
  - **Что:** `class AttendanceRepository(Protocol)` с методами:
    - `async def add(self, log: AttendanceLog) -> AttendanceLog`
    - `async def get_open_session_for_employee(self, employee_id: int) -> AttendanceLog | None`
    - `async def update(self, log: AttendanceLog) -> AttendanceLog` — для close/extend
    - `async def list(self, *, employee_id: int | None = None, zone_id: int | None = None, status: AttendanceStatus | None = None, started_from: datetime | None = None, started_to: datetime | None = None, limit: int = 50, offset: int = 0) -> list[AttendanceLog]`
    - `async def count(self, **filters) -> int`
    - `async def get_by_id(self, log_id: int) -> AttendanceLog | None`
  - **Логи:** не требуются (Protocol).

### Phase 2: Database migration

- [x] **Task 5: Alembic-миграция — добавить last_seen_at**
  - **Файлы:** `backend/alembic/versions/2026_05_02_*_add_last_seen_at.py`
  - **Что:** `ALTER TABLE attendance_logs ADD COLUMN last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()` (с дефолтом now() для совместимости с возможными существующими записями), затем убрать default `DROP DEFAULT` после backfill. Также добавить колонку в `AttendanceLogORM` в `backend/app/infrastructure/db/orm/attendance.py` (тип `Mapped[datetime]`, server_default=`func.now()` уже не нужен после миграции — но Mapped без default'а).
  - **Downgrade:** `ALTER TABLE attendance_logs DROP COLUMN last_seen_at`.
  - **Логи:** не требуются (миграция).

### Phase 3: Infrastructure

- [x] **Task 6: SqlAlchemyAttendanceRepository**
  - **Файлы:** `backend/app/infrastructure/repositories/attendance_repository.py`
  - **Что:** Класс `SqlAlchemyAttendanceRepository(AttendanceRepository)` по образцу `SqlAlchemyFingerprintRepository`. Методы: `add`, `get_open_session_for_employee` (запрос с `WHERE ended_at IS NULL AND employee_id = ? ORDER BY started_at DESC LIMIT 1` — использует partial index), `update`, `list` с динамическими фильтрами, `count`, `get_by_id`. Маппинг ORM ↔ domain через статический `_to_domain(orm) -> AttendanceLog`.
  - **Логи:** `log.debug("[attendance.repo.{method}] ...")` на старте каждого метода с параметрами; `log.info` на add/update с id результата.
  - **Транзакции:** `flush()` после `session.add()` (commit на уровне use case через session lifecycle).

### Phase 4: Application use cases

- [ ] **Task 7: RecordAttendanceUseCase**
  - **Файлы:** `backend/app/application/attendance/record_attendance.py`
  - **Что:**
    - `dataclass(frozen=True) RecordAttendanceCommand`: `employee_id: int`, `zone_id: int`, `zone_type: ZoneType`, `now: datetime`.
    - `RecordAttendanceUseCase` с зависимостями `AttendanceRepository`, `EmployeeRepository` (для получения `schedule_start/end`), `inactivity_timeout: timedelta`.
    - Метод `execute(cmd) -> AttendanceLog` реализует 5-веточную логику open/close/extend (см. раздел «Логика сессий»).
  - **Логи:** `log.debug("[attendance.record.execute] start", employee_id, zone_id, now)`. `log.info` на каждое action: `attendance.session.opened`, `attendance.session.closed`, `attendance.session.extended`, `attendance.session.timeout_close_then_open`. Поля: `session_id`, `duration_seconds`, `status`.
  - **Ошибки:** `NotFoundError` если `Employee` не найден, `ValidationError` если `now` без timezone.

- [ ] **Task 8: ListAttendanceUseCase**
  - **Файлы:** `backend/app/application/attendance/list_attendance.py`
  - **Что:**
    - `dataclass(frozen=True) ListAttendanceQuery`: все фильтры из repository.list + `requesting_user: Employee` (для self-only проверки).
    - `ListAttendanceUseCase` с зависимостью `AttendanceRepository`.
    - Метод `execute(query) -> tuple[list[AttendanceLog], int]` (логи + total count). Для `requesting_user.role == EMPLOYEE` принудительно подставить `employee_id = requesting_user.id` или `raise ForbiddenError` если просит чужие.
  - **Логи:** `log.debug("[attendance.list.execute] start", filters)`. `log.info("[attendance.list.execute] done", total)`.

- [ ] **Task 9: ComputeAttendanceSummaryUseCase**
  - **Файлы:** `backend/app/application/attendance/compute_summary.py`
  - **Что:**
    - `dataclass(frozen=True) AttendanceSummaryQuery`: `employee_id: int`, `period_from: datetime`, `period_to: datetime`, `requesting_user: Employee`.
    - `dataclass(frozen=True) AttendanceSummary`: `employee_id`, `period_from`, `period_to`, `work_hours_total: float`, `lateness_count: int`, `overtime_seconds_total: int`, `sessions_count: int`.
    - `ComputeAttendanceSummaryUseCase` — берёт все `AttendanceLog` сотрудника в периоде, агрегирует: `work_hours_total = сумма duration_seconds для зон workplace / 3600`, `lateness_count = count(status==LATE)`, `overtime_seconds_total = сумма duration_seconds для status==OVERTIME` (упрощённо — overtime считается полностью; точный расчёт overtime-секунд относительно schedule_end оставляем на следующую итерацию).
    - Self-only проверка как в ListAttendanceUseCase.
    - Открытые сессии (`ended_at IS NULL`) в агрегации игнорируются (длительность ещё не известна).
  - **Логи:** `log.info("[attendance.summary.execute] done", employee_id, work_hours, lateness_count)`.

### Phase 5: Presentation

- [ ] **Task 10: Pydantic-схемы**
  - **Файлы:** `backend/app/presentation/schemas/attendance.py`
  - **Что:**
    - `AttendanceLogResponse(BaseModel, extra=forbid)`: `id`, `employee_id`, `zone_id`, `started_at`, `ended_at`, `last_seen_at`, `duration_seconds`, `status: str` (enum value).
    - `AttendancePageResponse`: `items: list[AttendanceLogResponse]`, `total`, `limit`, `offset`.
    - `AttendanceSummaryResponse(BaseModel, extra=forbid)`: соответствует доменному `AttendanceSummary`.
  - **Логи:** не требуются.

- [ ] **Task 11: Router и dependency wiring**
  - **Файлы:** `backend/app/presentation/api/v1/attendance.py`, `backend/app/presentation/dependencies.py`, `backend/app/main.py`
  - **Что:**
    - В `dependencies.py`: добавить `get_attendance_repository`, `get_record_attendance_use_case`, `get_list_attendance_use_case`, `get_compute_attendance_summary_use_case`. Inactivity timeout из `Settings.attendance_inactivity_timeout_seconds` (новое поле в `app/core/config.py`, default 1800).
    - В `attendance.py`: router с двумя эндпоинтами:
      - `GET /api/v1/attendance` — фильтры через `Query(default=None)`, `limit/offset` валидируются как у employees, защита через `Depends(get_current_user)` (use case разруливает self vs admin).
      - `GET /api/v1/attendance/summary` — query params `employee_id`, `from`, `to`.
    - В `main.py`: подключить `attendance.router` через `app.include_router`.
  - **Логи:** `log.info("[api.attendance.list] start", filters)` / `done`. То же для summary.

- [ ] **Task 12: Интеграция с classify-эндпоинтом**
  - **Файлы:** `backend/app/presentation/api/v1/positioning.py`, `backend/app/presentation/dependencies.py`
  - **Что:** В функции `classify_location` после успешного `use_case.execute(cmd)` вызвать `record_attendance_use_case.execute(RecordAttendanceCommand(employee_id=current_user.id, zone_id=result.zone_id, zone_type=result.zone_type, now=datetime.now(tz=UTC)))`. `RecordAttendanceUseCase` инжектится через `Depends(get_record_attendance_use_case)`. Если `record_attendance` поднимает исключение — оно НЕ должно ломать ответ classify (логировать `log.warning("[positioning.classify.attendance_record_failed] ...", exc_info=exc)`). Возвращаемый `ClassifyResponse` остаётся прежним (без изменения схемы).
  - **Логи:** `log.info("[positioning.classify.attendance_recorded] ...", session_id, status)` после успешной записи.

### Phase 6: Tests

- [ ] **Task 13: FakeAttendanceRepository + unit-тесты use cases**
  - **Файлы:** `backend/tests/unit/application/fakes.py` (расширить), `backend/tests/unit/application/test_record_attendance.py`, `test_list_attendance.py`, `test_compute_attendance_summary.py`
  - **Что:**
    - В `fakes.py`: `FakeAttendanceRepository` со словарём `_storage`, поддержкой всех фильтров и `get_open_session_for_employee` через scan.
    - `test_record_attendance.py` (минимум 6 тестов): открытие новой сессии без активной, продление при той же зоне в пределах timeout, закрытие+открытие при смене зоны, закрытие+открытие при таймауте в той же зоне, статус `late` при `started_at > schedule_start`, отсутствие графика → `present` без late.
    - `test_list_attendance.py` (4 теста): фильтрация по employee_id + диапазону, self-only для employee, admin видит чужих, корректная total.
    - `test_compute_attendance_summary.py` (4 теста): корректный work_hours, lateness_count, overtime_seconds, открытые сессии исключены.
  - **Логи:** в тестах — нет.
  - **Маркер:** `pytestmark = pytest.mark.unit`.

- [ ] **Task 14: Integration-тесты API**
  - **Файлы:** `backend/tests/integration/api/test_attendance.py`
  - **Что:** Запуск через `client_with_db` + `db_engine` (testcontainers). Сценарии:
    - Seed: создать employee, zone (workplace), сделать `POST /classify` → проверить, что `GET /attendance?employee_id=X` вернёт 1 открытую сессию.
    - Сделать второй `/classify` в другой зоне → 2 сессии (одна закрыта с duration > 0).
    - Self-only: employee A не может смотреть логи employee B (403).
    - Summary: создать 3 сессии в workplace на разные дни → проверить `work_hours_total`.
  - **Логи:** не требуются.
  - **Маркер:** `pytestmark = pytest.mark.integration`.

### Phase 7: Документация

- [ ] **Task 15: backend/README + docs/attendance.md**
  - **Файлы:** `backend/README.md` (раздел attendance), `docs/attendance.md` (новый)
  - **Что:** В `backend/README.md` — краткое описание endpoints `/api/v1/attendance` и `/api/v1/attendance/summary`, env-переменная `ATTENDANCE_INACTIVITY_TIMEOUT_SECONDS`. В `docs/attendance.md` — детальное описание логики сессий (5 веток), семантики статусов (present/late/overtime), как `/classify` авто-создаёт сессии, как считается `work_hours_total`, лимиты MVP (открытые сессии исключены из summary, overtime считается всю длительность сессии).
  - **Язык:** русский.

## Commit Plan

15 задач — нужны checkpoint-коммиты:

- **Checkpoint 1 (после Task 4):** `feat(attendance): доменный слой — entities, value objects, repository protocol, services`
- **Checkpoint 2 (после Task 6):** `feat(attendance): миграция last_seen_at + SQLAlchemy-репозиторий`
- **Checkpoint 3 (после Task 9):** `feat(attendance): use cases — record, list, compute summary`
- **Checkpoint 4 (после Task 12):** `feat(api): эндпоинты /api/v1/attendance + интеграция с /classify`
- **Checkpoint 5 (после Task 14):** `test(attendance): unit + integration тесты use cases и API`
- **Final commit (после Task 15):** `docs(attendance): README + руководство по логике сессий`

## Принципы

1. Domain-слой не импортирует sqlalchemy/fastapi/scikit-learn — только stdlib + pydantic для валидации.
2. Все datetime — timezone-aware (`tz=UTC`). Валидация в `__post_init__`.
3. Гиперпараметры (inactivity timeout) — через config, без magic-чисел.
4. Use cases получают зависимости через Protocols (`AttendanceRepository`, `EmployeeRepository`), не конкретные классы.
5. Self-only проверка для роли `employee` — на уровне use case, не в роутере.
6. Интеграция с `/classify` — через композицию в presentation-слое (router вызывает оба use case), не через импорт `attendance` из `positioning` модуля.
7. Открытые сессии (`ended_at IS NULL`) исключены из агрегаций.
