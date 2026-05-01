<!-- handoff:task:1e8f0ad6-9f16-47e6-9439-3da642eec713 -->

# Implementation Plan: База данных и миграции

Branch: feature/backend-database-migrations-1e8f0a
Created: 2026-05-01

## Settings

- Testing: yes (pytest для всех слоёв; интеграционные тесты с реальным PostgreSQL)
- Logging: verbose (structlog с DEBUG-уровнем; LOG_LEVEL контролирует продакшен)
- Docs: yes (обязательный чекпоинт документации в `/aif-implement` финале)

## Roadmap Linkage

Milestone: "База данных и миграции"
Rationale: Этот план реализует третью веху роадмапа — слой персистентности backend-сервиса (PostgreSQL + SQLAlchemy 2.x async + Alembic + базовые ORM-модели), который служит фундаментом для последующих вех «Аутентификация», «Управление сотрудниками и зонами», «Приём радиоотпечатков и калибровка», «ML-классификаторы» и «Учёт рабочего времени».

## Цель плана

Реализовать слой работы с PostgreSQL для backend-сервиса по принципам Clean Architecture:

- Async-подключение к PostgreSQL через SQLAlchemy 2.x + asyncpg
- Базовый `DeclarativeBase` с naming convention для constraint'ов (важно для предсказуемого autogenerate)
- ORM-модели четырёх ключевых сущностей: `employees`, `zones`, `fingerprints`, `attendance_logs` — в `app/infrastructure/db/orm/` (Clean Architecture: domain не знает об ORM)
- Alembic-миграции в async-режиме + начальная миграция со всей схемой
- FastAPI dependency `get_session()` с управлением транзакциями (commit on success, rollback on error)
- Управление engine pool через FastAPI lifespan (open on startup, dispose on shutdown)
- Замена заглушки `_check_database()` в healthcheck на реальный `SELECT 1` с таймаутом
- Seed-скрипт `scripts/seed.py` для быстрого наполнения dev-БД (4 зоны, 1 admin-сотрудник, тестовый набор калибровочных отпечатков)
- Интеграционные тесты: проверка `alembic upgrade head` ↔ `downgrade base`, обновлённый healthcheck-тест с настоящей БД

После плана у нас должно быть:

- `alembic upgrade head` создаёт пустую схему с 4 таблицами + enum-типами
- `python scripts/seed.py` наполняет dev-БД тестовыми данными
- `curl /api/v1/health` возвращает `checks.database = "ok"` при живой БД и `"fail"` при остановленной
- `pytest -m integration` проходит на CI/локально с testcontainer-postgres

## Commit Plan

- **Commit 1** (после задач 1-3): `chore(backend): добавить SQLAlchemy 2 + asyncpg + alembic, настроить async session factory`
- **Commit 2** (после задач 4-7): `feat(db): ORM-модели employees, zones, fingerprints, attendance_logs`
- **Commit 3** (после задач 8-9): `feat(db): настроить alembic и зафиксировать initial миграцию`
- **Commit 4** (после задач 10-12): `feat(api): подключить healthcheck к реальной БД через SELECT 1`
- **Commit 5** (после задачи 13): `chore(db): добавить seed-скрипт для dev-окружения`
- **Commit 6** (после задач 14-16): `test(backend): интеграционные тесты миграций и healthcheck`
- **Commit 7** (после задачи 17): `docs: руководство по БД и миграциям в backend/README.md`

## Tasks

### Phase 1: Зависимости и базовая настройка БД

- [x] **Task 1: Добавить SQLAlchemy 2.x, asyncpg, alembic в `pyproject.toml`**
  - **Deliverable:** обновлённый `backend/pyproject.toml` с production-зависимостями и dev-зависимостями
  - **Production dependencies (добавить):**
    - `sqlalchemy[asyncio]>=2.0.36,<3.0.0`
    - `asyncpg>=0.29.0,<0.31.0`
    - `alembic>=1.13.0,<2.0.0`
    - `greenlet>=3.0.0,<4.0.0` (требуется SQLAlchemy для async-моста)
  - **Dev dependencies (добавить):**
    - `testcontainers[postgresql]>=4.7.0,<5.0.0` (поднимает Postgres-контейнер для интеграционных тестов)
    - `psycopg[binary]>=3.2.0,<4.0.0` (нужен alembic для синхронных операций offline-режима + удобен для seed-скрипта)
  - **Coverage omit:** добавить `alembic/versions/*` в `[tool.coverage.run].omit` (миграции не должны учитываться в покрытии)
  - **Файлы:** `backend/pyproject.toml` (модификация)
  - **LOGGING REQUIREMENTS:** N/A (конфиг)
  - **Acceptance:** `cd backend && pip install -e .[dev]` отрабатывает; `python -c "import sqlalchemy; import alembic; import asyncpg; print(sqlalchemy.__version__)"` выдаёт версию ≥ 2.0.36

- [x] **Task 2: Реализовать `app/infrastructure/db/session.py` — async engine + sessionmaker + FastAPI dependency**
  - **Deliverable:**
    - Module-level singleton: `_engine: AsyncEngine | None = None`, `_sessionmaker: async_sessionmaker[AsyncSession] | None = None`
    - Функция `init_engine(settings: Settings) -> AsyncEngine` — создаёт `AsyncEngine` с настройками pool:
      - `pool_size=5, max_overflow=10, pool_pre_ping=True, pool_recycle=1800`
      - `echo=settings.environment == "development" and settings.log_level == "DEBUG"` (SQL-логи только в dev+DEBUG, иначе шум)
      - `connect_args={"server_settings": {"jit": "off"}}` (рекомендация Supabase: JIT часто ухудшает простые запросы Postgres)
    - Функция `dispose_engine() -> None` — корректно закрывает pool
    - Функция `get_sessionmaker() -> async_sessionmaker[AsyncSession]` — fail fast если `init_engine` не вызван
    - Async-генератор `get_session() -> AsyncIterator[AsyncSession]`:
      - Открывает session
      - На выход успешного хендлера — `commit()`
      - На исключение — `rollback()` и rethrow
      - Гарантированно закрывает session в `finally`
    - Используется как FastAPI dependency: `session: AsyncSession = Depends(get_session)`
  - **Файлы:** `backend/app/infrastructure/db/session.py` (новый)
  - **LOGGING REQUIREMENTS:**
    - В `init_engine`: на INFO `[db.session.init_engine] engine created pool_size={pool_size} max_overflow={max_overflow}` (НЕ логировать DSN целиком — только `database_url.host` и `path` без credentials)
    - В `dispose_engine`: на INFO `[db.session.dispose_engine] engine disposed`
    - В `get_session` на DEBUG (только при DEBUG, иначе шум на каждый запрос): `[db.session] session opened` / `[db.session] session committed` / `[db.session] session rollback exc_type={type}`
    - При rollback — на WARN `[db.session] rollback due to exception exc_type={type}` (всегда, не только DEBUG)
  - **Acceptance:** unit-тест с моковым engine: `init_engine` создаёт engine, `dispose_engine` его закрывает; `get_session` коммитит при успехе и откатывает при исключении

- [x] **Task 3: Реализовать `app/infrastructure/db/base.py` — DeclarativeBase с naming convention + TimestampMixin**
  - **Deliverable:**
    - Класс `Base(DeclarativeBase)` с `metadata = MetaData(naming_convention=...)`
    - Naming convention (стандарт Alembic + SQLAlchemy для предсказуемого autogenerate):
      ```python
      NAMING_CONVENTION = {
          "ix": "ix_%(column_0_label)s",
          "uq": "uq_%(table_name)s_%(column_0_name)s",
          "ck": "ck_%(table_name)s_%(constraint_name)s",
          "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
          "pk": "pk_%(table_name)s",
      }
      ```
    - `TimestampMixin`:
      ```python
      class TimestampMixin:
          created_at: Mapped[datetime] = mapped_column(
              DateTime(timezone=True), server_default=func.now(), nullable=False
          )
          updated_at: Mapped[datetime] = mapped_column(
              DateTime(timezone=True),
              server_default=func.now(),
              onupdate=func.now(),
              nullable=False,
          )
      ```
    - Type aliases для частых mapped-типов (опционально): `BigIntPK = Annotated[int, mapped_column(BigInteger, Identity(always=False), primary_key=True)]`
  - **Файлы:** `backend/app/infrastructure/db/base.py` (новый)
  - **LOGGING REQUIREMENTS:** N/A (декларации классов)
  - **Acceptance:** `from app.infrastructure.db.base import Base` импортируется; `Base.metadata.naming_convention` содержит ключи `ix, uq, ck, fk, pk`

### Phase 2: ORM-модели

- [x] **Task 4: ORM-модель `Employee` в `app/infrastructure/db/orm/employees.py`**
  - **Deliverable:**
    - Enum `Role` (Python-enum): `ADMIN`, `EMPLOYEE`
    - SQLAlchemy enum-тип: `RoleEnum = SqlEnum(Role, name="role_enum", native_enum=True, create_type=True)`
    - Класс `Employee(Base, TimestampMixin)`, `__tablename__ = "employees"`:
      - `id: Mapped[int]` — `BigInteger`, `Identity(always=False)`, primary_key
      - `email: Mapped[str]` — `String(255)`, `unique=True`, `nullable=False`, `index=True`
      - `full_name: Mapped[str]` — `String(255)`, `nullable=False`
      - `role: Mapped[Role]` — `RoleEnum`, `nullable=False`, default `Role.EMPLOYEE`
      - `hashed_password: Mapped[str]` — `String(255)`, `nullable=False` (хеширование добавим на вехе «Аутентификация», пока — placeholder)
      - `is_active: Mapped[bool]` — `Boolean`, `nullable=False`, `server_default=text("true")`
      - `schedule_start: Mapped[time | None]` — `Time(timezone=False)`, `nullable=True` (плановое начало рабочего дня)
      - `schedule_end: Mapped[time | None]` — `Time(timezone=False)`, `nullable=True` (плановый конец)
    - `__table_args__`:
      - `Index("ix_employees_role_active", "role", "is_active")` — для фильтрации админов и активных сотрудников
      - `CheckConstraint("schedule_start IS NULL OR schedule_end IS NULL OR schedule_start < schedule_end", name="schedule_order")`
    - relationship `attendance_logs` объявить через TYPE_CHECKING / forward-ref, реальная связь — через `back_populates` в Task 7
  - **Файлы:** `backend/app/infrastructure/db/orm/employees.py` (новый)
  - **LOGGING REQUIREMENTS:** N/A (декларация ORM-модели)
  - **Acceptance:** unit-тест: `Employee.__tablename__ == "employees"`, `Employee.metadata is Base.metadata`; `Role.ADMIN.value == "admin"`

- [x] **Task 5: ORM-модель `Zone` в `app/infrastructure/db/orm/zones.py`**
  - **Deliverable:**
    - Python enum `ZoneType`: `WORKPLACE`, `CORRIDOR`, `MEETING_ROOM`, `OUTSIDE_OFFICE` (точно соответствует доменной классификации в [.ai-factory/DESCRIPTION.md](../DESCRIPTION.md))
    - SQLAlchemy enum-тип: `ZoneTypeEnum = SqlEnum(ZoneType, name="zone_type_enum", native_enum=True, create_type=True)`
    - Класс `Zone(Base, TimestampMixin)`, `__tablename__ = "zones"`:
      - `id: Mapped[int]` — `BigInteger`, `Identity(always=False)`, primary_key
      - `name: Mapped[str]` — `String(100)`, `unique=True`, `nullable=False`
      - `type: Mapped[ZoneType]` — `ZoneTypeEnum`, `nullable=False`
      - `description: Mapped[str | None]` — `Text`, `nullable=True`
      - `display_color: Mapped[str | None]` — `String(7)`, `nullable=True` (HEX `#RRGGBB`, для веб-визуализации радиокарты)
    - `__table_args__`:
      - `Index("ix_zones_type", "type")`
      - `CheckConstraint("display_color IS NULL OR display_color ~ '^#[0-9A-Fa-f]{6}$'", name="display_color_hex")`
  - **Файлы:** `backend/app/infrastructure/db/orm/zones.py` (новый)
  - **LOGGING REQUIREMENTS:** N/A
  - **Acceptance:** unit-тест: `Zone.__tablename__ == "zones"`; все 4 значения `ZoneType` присутствуют

- [x] **Task 6: ORM-модель `Fingerprint` в `app/infrastructure/db/orm/radiomap.py`**
  - **Deliverable:**
    - Класс `Fingerprint(Base, TimestampMixin)`, `__tablename__ = "fingerprints"`:
      - `id: Mapped[int]` — `BigInteger`, `Identity(always=False)`, primary_key
      - `employee_id: Mapped[int | None]` — `BigInteger`, `ForeignKey("employees.id", ondelete="SET NULL")`, `nullable=True`, `index=True` (nullable: калибровочные отпечатки могут быть привязаны к зоне без employee)
      - `zone_id: Mapped[int | None]` — `BigInteger`, `ForeignKey("zones.id", ondelete="SET NULL")`, `nullable=True`, `index=True` (nullable: live-отпечатки не привязаны к зоне до классификации)
      - `is_calibration: Mapped[bool]` — `Boolean`, `nullable=False`, `server_default=text("false")` (true для эталонных точек admin-режима)
      - `captured_at: Mapped[datetime]` — `DateTime(timezone=True)`, `nullable=False` (время захвата отпечатка на устройстве)
      - `device_id: Mapped[str | None]` — `String(64)`, `nullable=True` (Android device_id для отладки)
      - `rssi_vector: Mapped[dict]` — `JSONB`, `nullable=False` (формат: `{"BSSID-1": -45, "BSSID-2": -67, ...}`)
      - `sample_count: Mapped[int]` — `Integer`, `nullable=False`, `server_default=text("1")` (число агрегированных сканов)
    - `__table_args__`:
      - `CheckConstraint("sample_count > 0", name="sample_count_positive")`
      - `CheckConstraint("(is_calibration = false) OR (zone_id IS NOT NULL)", name="calibration_requires_zone")` (важный инвариант: калибровочный отпечаток должен иметь zone)
      - `Index("ix_fingerprints_employee_captured", "employee_id", "captured_at")` — для выборки последних отпечатков сотрудника
      - `Index("ix_fingerprints_zone_calibration", "zone_id", "is_calibration")` — для построения калибровочного набора по зоне
  - **Файлы:** `backend/app/infrastructure/db/orm/radiomap.py` (новый)
  - **LOGGING REQUIREMENTS:** N/A
  - **Acceptance:** unit-тест: `Fingerprint.__tablename__ == "fingerprints"`; check_constraints видны в `Fingerprint.__table__.constraints`

- [x] **Task 7: ORM-модель `AttendanceLog` в `app/infrastructure/db/orm/attendance.py`**
  - **Deliverable:**
    - Python enum `AttendanceStatus`: `PRESENT`, `LATE`, `ABSENT`, `OVERTIME`
    - SQLAlchemy enum-тип: `AttendanceStatusEnum = SqlEnum(AttendanceStatus, name="attendance_status_enum", native_enum=True, create_type=True)`
    - Класс `AttendanceLog(Base, TimestampMixin)`, `__tablename__ = "attendance_logs"`:
      - `id: Mapped[int]` — `BigInteger`, `Identity(always=False)`, primary_key
      - `employee_id: Mapped[int]` — `BigInteger`, `ForeignKey("employees.id", ondelete="CASCADE")`, `nullable=False`, `index=True`
      - `zone_id: Mapped[int]` — `BigInteger`, `ForeignKey("zones.id", ondelete="RESTRICT")`, `nullable=False` (RESTRICT: нельзя удалить зону, на которую есть логи; для чистки — soft-delete или явная миграция)
      - `started_at: Mapped[datetime]` — `DateTime(timezone=True)`, `nullable=False`
      - `ended_at: Mapped[datetime | None]` — `DateTime(timezone=True)`, `nullable=True` (NULL = открытая сессия, сотрудник ещё в зоне)
      - `duration_seconds: Mapped[int | None]` — `Integer`, `nullable=True` (вычисляется на close сессии; null пока сессия открыта)
      - `status: Mapped[AttendanceStatus]` — `AttendanceStatusEnum`, `nullable=False`, default `AttendanceStatus.PRESENT`
    - `__table_args__`:
      - `CheckConstraint("ended_at IS NULL OR ended_at > started_at", name="ended_after_started")`
      - `CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="duration_non_negative")`
      - `Index("ix_attendance_logs_employee_started", "employee_id", "started_at")` — для отчётов по сотруднику за период
      - `Index("ix_attendance_logs_zone", "zone_id")`
      - `Index("ix_attendance_logs_open_sessions", "employee_id", postgresql_where=text("ended_at IS NULL"))` — partial-index для активных сессий (быстрый поиск «кто сейчас на работе»)
  - **Файлы:** `backend/app/infrastructure/db/orm/attendance.py` (новый)
  - **LOGGING REQUIREMENTS:** N/A
  - **Acceptance:** unit-тест: `AttendanceLog.__tablename__ == "attendance_logs"`; partial-index присутствует в `__table_args__`

### Phase 3: Alembic

- [x] **Task 8: Настроить Alembic в async-режиме**
  - **Deliverable:**
    - `backend/alembic.ini` с минимально необходимой конфигурацией; `sqlalchemy.url` НЕ задаётся в ini (берётся из `Settings.database_url` в `env.py`); `script_location = alembic`; `prepend_sys_path = .`; шаблон файла версии — `%%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s` (читаемые таймстампы)
    - `backend/alembic/env.py`:
      - Импорт `Settings` через `get_settings()`
      - Импорт `Base` из `app.infrastructure.db.base`
      - **Импорт всех ORM-модулей** (`employees`, `zones`, `radiomap`, `attendance`) для регистрации моделей в `Base.metadata`
      - `target_metadata = Base.metadata`
      - `compare_type=True`, `compare_server_default=True` (для качественного autogenerate)
      - `include_schemas=False` (один schema `public`)
      - `render_as_batch=False` (Postgres поддерживает ALTER TABLE)
      - **Online-режим — async**:
        ```python
        async def run_async_migrations() -> None:
            connectable = create_async_engine(settings.database_url.unicode_string(), poolclass=NullPool)
            async with connectable.connect() as connection:
                await connection.run_sync(do_run_migrations)
            await connectable.dispose()
        ```
      - **Offline-режим**: использовать `Settings.database_url` для генерации SQL-скриптов
    - `backend/alembic/script.py.mako` — стандартный mako-шаблон (`alembic init` создаёт сам, оставить)
    - `backend/alembic/versions/.gitkeep` — placeholder (директория будет наполняться)
    - В `pyproject.toml` добавить `[tool.alembic]` (если нужно) или оставить только `alembic.ini`
  - **Файлы:** `backend/alembic.ini` (новый), `backend/alembic/env.py` (новый), `backend/alembic/script.py.mako` (новый), `backend/alembic/versions/.gitkeep`
  - **LOGGING REQUIREMENTS:**
    - В `env.py.run_migrations_online`: `[alembic.env.online] start url_host={host} schema={schema}` на INFO (через stdlib logging, чтобы alembic-вывод сохранялся)
    - На завершение: `[alembic.env.online] done revision={head_rev}`
  - **Acceptance:** `cd backend && alembic current` выводит «нет ревизий» без ошибок (env.py загружается, settings парсятся); `alembic check` (если ревизий ещё нет) не падает

- [x] **Task 9: Сгенерировать и зафиксировать initial-миграцию `0001_initial_schema.py`**
  - **Deliverable:**
    - Запустить локально `cd backend && alembic revision --autogenerate -m "initial schema"` против чистой БД
    - Получить файл `backend/alembic/versions/<timestamp>-<rev>_initial_schema.py`
    - **Вручную проверить** содержимое:
      - Все 4 таблицы созданы (`employees`, `zones`, `fingerprints`, `attendance_logs`)
      - Все 3 enum-типа созданы (`role_enum`, `zone_type_enum`, `attendance_status_enum`)
      - Все индексы (включая partial `ix_attendance_logs_open_sessions`) присутствуют
      - Все CHECK constraints зафиксированы
      - FK-направления верны (employees ← fingerprints, zones ← fingerprints, employees ← attendance_logs, zones ← attendance_logs)
      - `downgrade()` корректно удаляет в обратном порядке (сначала таблицы, потом enum-типы)
    - При необходимости — отредактировать миграцию (особенно partial-index, autogenerate иногда упускает `postgresql_where`)
    - Проверить idempotency: `alembic upgrade head && alembic downgrade base && alembic upgrade head` отрабатывает чисто
  - **Файлы:** `backend/alembic/versions/<timestamp>-<rev>_initial_schema.py` (новый, autogenerate + ручная правка)
  - **LOGGING REQUIREMENTS:** N/A (миграции используют alembic-логгер)
  - **Acceptance:** на локальной БД `alembic upgrade head` создаёт схему, `\dt` показывает 4 таблицы + `alembic_version`, `\dT` показывает 3 enum-типа; `alembic downgrade base` чисто всё удаляет

### Phase 4: Healthcheck и lifespan

- [x] **Task 10: Реализовать `app/infrastructure/db/healthcheck.py` — проверка БД через `SELECT 1`**
  - **Deliverable:**
    - Функция `async def check_database(session_factory: async_sessionmaker[AsyncSession], timeout_seconds: float = 2.0) -> Literal["ok", "fail"]`:
      - Открывает session через `session_factory()`
      - Выполняет `await session.execute(select(literal(1)))` (или `text("SELECT 1")`)
      - Оборачивает в `asyncio.wait_for(..., timeout=timeout_seconds)` — health не должен висеть на сетевых проблемах
      - На любое исключение (`SQLAlchemyError`, `asyncio.TimeoutError`, `ConnectionRefusedError`) возвращает `"fail"` и логирует на WARN
      - На успех возвращает `"ok"`
  - **Файлы:** `backend/app/infrastructure/db/healthcheck.py` (новый)
  - **LOGGING REQUIREMENTS:**
    - На вход (DEBUG): `[db.healthcheck] start timeout={s}`
    - На успех (DEBUG): `[db.healthcheck] ok latency_ms={ms}`
    - На fail (WARN, не ERROR — это ожидаемое состояние при остановленной БД): `[db.healthcheck] fail reason={short_reason} exc_type={type}` — без полного stacktrace в проде
    - НЕ логировать DSN или credentials
  - **Acceptance:** unit-тест с моковой session, бросающей `ConnectionRefusedError`, возвращает `"fail"` и пишет WARN; с successful execute возвращает `"ok"`

- [x] **Task 11: Обновить `app/presentation/api/v1/health.py` — реальный SELECT 1 через DI**
  - **Deliverable:**
    - В `health_check` endpoint заменить вызов локального `_check_database()` на DI-инъекцию проверки:
      ```python
      session_factory: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker_dep)
      ...
      checks["database"] = await check_database(session_factory)
      ```
    - Реализовать `get_sessionmaker_dep()` в `app/presentation/dependencies.py` (новый файл) — обёртка над `app.infrastructure.db.session.get_sessionmaker()`
    - Удалить локальную заглушку `_check_database()` из `health.py`
    - При `status="degraded"` (хоть один check = fail) — возвращать **200 OK** (не 503): healthcheck должен отвечать всегда; degraded — это сигнал для оператора, а не auth-failure для балансировщика. (Если позже потребуется отдельный `liveness` vs `readiness` — добавим эндпоинт `/api/v1/ready` с 503 на degraded.)
  - **Файлы:** `backend/app/presentation/api/v1/health.py` (модификация), `backend/app/presentation/dependencies.py` (новый)
  - **LOGGING REQUIREMENTS:**
    - На degraded: уже есть WARN `[health.check] degraded failed_checks=[...]` — оставить
    - Дополнительно при database = fail: убедиться, что причина (exception type) логируется на уровне `check_database` (Task 10), не дублируем здесь
  - **Acceptance:** при поднятой БД `curl /api/v1/health` возвращает 200 + `checks.database = "ok"`; при остановленной БД — 200 + `checks.database = "fail"` + `status = "degraded"`

- [x] **Task 12: Обновить `app/main.py` lifespan — открыть/закрыть engine pool на startup/shutdown**
  - **Deliverable:**
    - В `_lifespan` контекстном менеджере:
      - **На startup**: `init_engine(settings)` (settings берём через `get_settings()`)
      - **На shutdown**: `await dispose_engine()`
      - Логировать каждое событие на INFO
      - При исключении на startup — логировать ERROR `exc_info=True` и пробросить (fail fast — не запускаем app в кривом состоянии)
    - НЕ создавать engine на module-level (только через lifespan)
  - **Файлы:** `backend/app/main.py` (модификация)
  - **LOGGING REQUIREMENTS:**
    - `[main.lifespan] startup begin`, `[main.lifespan] db engine ready`, `[main.lifespan] startup complete` на INFO
    - `[main.lifespan] shutdown begin`, `[main.lifespan] db engine disposed`, `[main.lifespan] shutdown complete` на INFO
    - На ошибке startup: `[main.lifespan] startup failed exc_type={type}` на ERROR с `exc_info=True`
  - **Acceptance:** `uvicorn app.main:app` логирует startup-цепочку при поднятии и shutdown-цепочку при Ctrl+C; при недоступной БД (DATABASE_URL указывает на несуществующий хост) сервер ВСЁ ЕЩЁ стартует (engine создаётся lazy, реальное подключение проверяется только в healthcheck) — это намеренно, чтобы не блокировать запуск ради БД, но healthcheck сразу покажет fail

### Phase 5: Seed-скрипт

- [x] **Task 13: Создать `backend/scripts/seed.py` — тестовые данные для dev-окружения**
  - **Deliverable:**
    - CLI-скрипт (запускается как `python -m scripts.seed` или `python scripts/seed.py`)
    - Инициализирует engine через `init_engine(get_settings())`
    - **Idempotency**: использовать `INSERT ... ON CONFLICT DO NOTHING` на уникальных полях (например `zones.name`, `employees.email`) — повторный запуск не падает
    - **Содержимое seed**:
      - 4 зоны: «Рабочее место А1» (workplace), «Рабочее место Б3» (workplace), «Коридор южный» (corridor), «Переговорная Малая» (meeting_room) + одна `outside_office` зона-маркер «Вне офиса»
      - 1 admin-сотрудник: `email=admin@svetlyachok.local`, `full_name=Админ Тестовый`, `role=ADMIN`, `hashed_password=PLACEHOLDER_seed_only` (заменим на реальный bcrypt-хеш на вехе аутентификации; пока — литерал, чтобы поле было заполнено)
      - 1 employee: `email=employee@svetlyachok.local`, `full_name=Иванов Иван Иванович`, `role=EMPLOYEE`, schedule 09:00-18:00
      - 3 калибровочных fingerprint: по одному на «Рабочее место А1», «Коридор южный», «Переговорная Малая» (с фиктивным RSSI-вектором: `{"AA:BB:CC:DD:EE:01": -45, "AA:BB:CC:DD:EE:02": -65, "AA:BB:CC:DD:EE:03": -75}`)
    - В конце вывести summary: «Создано: 5 zones, 2 employees, 3 fingerprints (новых: N, обновлено: 0)»
    - В `pyproject.toml` добавить `scripts/` в `[tool.hatch.build.targets.wheel]` packages (или оставить вне пакета — чисто dev-инструмент)
  - **Файлы:** `backend/scripts/__init__.py` (пустой), `backend/scripts/seed.py` (новый)
  - **LOGGING REQUIREMENTS:**
    - На старте: `[seed] start environment={env} database_host={host}` на INFO
    - На каждый раздел: `[seed.zones] inserted={n} skipped={m}`, `[seed.employees] inserted={n} skipped={m}`, `[seed.fingerprints] inserted={n} skipped={m}` на INFO
    - На ошибке: ERROR с `exc_info=True` и exit code 1
  - **Acceptance:** `cd backend && python scripts/seed.py` отрабатывает на пустой БД (после `alembic upgrade head`) и создаёт записи; повторный запуск не падает и логирует `skipped > 0`

### Phase 6: Тесты

- [x] **Task 14: Обновить `backend/tests/conftest.py` — testcontainer Postgres + транзакционные сессии**
  - **Deliverable:**
    - Добавить session-scoped fixture `postgres_container` (testcontainers `PostgresContainer`):
      - Поднимает контейнер `postgres:16-alpine` один раз на test session
      - Возвращает DSN
      - В CI можно переопределить через `TEST_DATABASE_URL` env var (не поднимать контейнер, использовать готовую тестовую БД)
    - Session-scoped fixture `migrated_db(postgres_container)`:
      - Запускает `alembic upgrade head` на тестовой БД (один раз)
    - Function-scoped fixture `db_session(migrated_db)`:
      - Открывает Connection + begin nested transaction (savepoint pattern)
      - Yield session, привязанную к этой transaction
      - На teardown — `await tx.rollback()` → каждый тест получает чистую БД без долгих pre/post hooks
    - Function-scoped fixture `db_sessionmaker(migrated_db)`:
      - Возвращает `async_sessionmaker` для тестов, которым нужна именно фабрика (например, `check_database`)
    - Обновить `app(settings, db_sessionmaker)`-fixture: переопределить `get_sessionmaker_dep` в FastAPI dependency-overrides на тестовый
    - Добавить marker-aware skip: `@pytest.mark.integration` тесты пропускаются, если `TEST_DATABASE_URL` не задан и docker недоступен (чтобы локальный `pytest -m unit` не падал)
  - **Файлы:** `backend/tests/conftest.py` (модификация), `backend/tests/integration/conftest.py` (модификация), `backend/.env.test` (модификация — добавить `TEST_DATABASE_URL=postgresql+asyncpg://...` с пометкой «опционально»)
  - **LOGGING REQUIREMENTS:** N/A (тестовая инфраструктура)
  - **Acceptance:** `pytest -m integration -v` проходит локально (если есть docker) и собирает корректные тесты в режиме `--collect-only`

- [x] **Task 15: Тесты `tests/integration/db/test_migrations.py` — alembic upgrade/downgrade**
  - **Deliverable:**
    - `backend/tests/integration/db/__init__.py` (пустой)
    - `test_upgrade_creates_all_tables`: после `alembic upgrade head` ожидаемые таблицы (`employees`, `zones`, `fingerprints`, `attendance_logs`, `alembic_version`) присутствуют в `information_schema.tables`
    - `test_upgrade_creates_all_enums`: ожидаемые enum-типы (`role_enum`, `zone_type_enum`, `attendance_status_enum`) присутствуют в `pg_type`
    - `test_downgrade_then_upgrade_idempotent`: `downgrade base` → `upgrade head` отрабатывает без ошибок и финальное состояние эквивалентно
    - `test_check_constraints_enforced`: попытка вставить `Fingerprint(is_calibration=True, zone_id=None)` падает с `IntegrityError` (срабатывает `calibration_requires_zone`)
    - `test_partial_index_for_open_sessions`: проверка через `pg_indexes`, что `ix_attendance_logs_open_sessions` имеет predicate `(ended_at IS NULL)`
  - **Файлы:** `backend/tests/integration/db/__init__.py`, `backend/tests/integration/db/test_migrations.py`
  - **LOGGING REQUIREMENTS:** N/A
  - **Acceptance:** `pytest tests/integration/db/test_migrations.py -v` зелёный

- [x] **Task 16: Тесты `tests/integration/api/test_health.py` — реальная БД-проверка в healthcheck**
  - **Deliverable:**
    - Добавить тест `test_health_database_ok`: `GET /api/v1/health` возвращает `checks.database = "ok"` при подключённом testcontainer-postgres
    - Добавить тест `test_health_database_fail_on_disposed_engine`: вручную `await dispose_engine()` → запрос возвращает `checks.database = "fail"` + `status = "degraded"`, response code остаётся 200
    - Сохранить существующие тесты на CorrelationID и базовый ok-кейс
  - **Файлы:** `backend/tests/integration/api/test_health.py` (модификация)
  - **LOGGING REQUIREMENTS:** N/A (тесты)
  - **Acceptance:** `pytest tests/integration/api/test_health.py -v` зелёный; coverage для `app/infrastructure/db/healthcheck.py` ≥ 80%

### Phase 7: Документация

- [x] **Task 17: Обновить `backend/README.md` — раздел «База данных и миграции»**
  - **Deliverable:**
    - Раздел «Локальный PostgreSQL»: `docker run -d --name svetlyachok-postgres -e POSTGRES_USER=svetlyachok -e POSTGRES_PASSWORD=dev_password -e POSTGRES_DB=svetlyachok -p 5432:5432 postgres:16-alpine` (одной командой) + ссылка на полноценный compose, который добавим на вехе «Развёртывание»
    - Раздел «Миграции»:
      - `alembic upgrade head` — применить все миграции
      - `alembic revision --autogenerate -m "описание"` — создать новую (плюс обязательное правило: каждый файл миграции ревьюится вручную, особенно partial-индексы и enum-изменения)
      - `alembic downgrade -1` — откатить последнюю
      - `alembic history -v` — посмотреть историю
      - `alembic current` — текущая версия
    - Раздел «Seed-данные»: `python scripts/seed.py` — наполнение dev-БД
    - Раздел «Тестирование с реальной БД»: упоминание testcontainers, env-переменная `TEST_DATABASE_URL` для CI
    - Раздел «Структура схемы»: краткое описание четырёх таблиц + ссылка на `.ai-factory/ARCHITECTURE.md`
    - Обновить раздел «Переменные окружения»: подтвердить, что `DATABASE_URL` обязательная и формат `postgresql+asyncpg://`
  - **Файлы:** `backend/README.md` (модификация); опционально пара пометок в `docs/getting-started.md` и `docs/architecture.md`, если они появились на предыдущей вехе
  - **LOGGING REQUIREMENTS:** N/A (документация)
  - **Acceptance:** новый раздел читается без перехода в исходники; команды копипастятся и работают на чистом dev-окружении

## Документационный чекпоинт (после Task 17)

В конце реализации `/aif-implement` остановится и предложит запустить `/aif-docs`. Документация должна включать:

- Раздел «База данных» в `backend/README.md` с командами установки, миграций, seed
- Описание ORM-схемы и инвариантов (CHECK constraints, partial-index)
- Описание процедуры создания и ревью миграций (правила в README.md и/или `docs/database-migrations.md`)

## Открытые вопросы

- **bcrypt** для `hashed_password` будет добавлен на вехе «Аутентификация (JWT)». Сейчас seed-скрипт пишет литерал-плейсхолдер; реальный хеш сгенерируется при создании пользователя через будущий `/api/v1/auth/register` (admin only).
- **Soft-delete vs hard-delete** для employees/zones — пока не делаем (FK ondelete=SET NULL для fingerprints, RESTRICT для attendance_logs). Если бизнес-логика на вехах CRUD/учёт времени потребует архивации — добавим столбец `archived_at: datetime | None`.
- **Multi-tenancy** не предусматривается — пилот в одном вузе. Если позже потребуется (например, разные институты) — добавим `organization_id` через миграцию.
- **Партицирование `fingerprints` и `attendance_logs`** не делаем (объёмы пилота — десятки тысяч записей, а не миллиарды). Если по итогам полевых испытаний таблицы превысят 10M строк — рассмотрим range-partitioning по `captured_at`/`started_at`.
