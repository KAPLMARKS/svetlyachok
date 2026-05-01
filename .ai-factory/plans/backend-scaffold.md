<!-- handoff:task:e190a548-068b-4e54-bc9e-8078336c0596 -->

# Implementation Plan: Базовый каркас backend (FastAPI + Clean Architecture)

Branch: feature/backend-fastapi-clean-architecture-e190a5
Created: 2026-05-01

## Settings

- Testing: yes (pytest для всех слоёв)
- Logging: verbose (structlog с DEBUG-уровнем; LOG_LEVEL контролирует продакшен)
- Docs: yes (обязательный чекпоинт документации в `/aif-implement` финале)

## Roadmap Linkage

Milestone: "Базовый каркас backend"
Rationale: Этот план реализует вторую веху роадмапа — каркас FastAPI приложения по Clean Architecture, который служит основой для всех последующих ML и API фич.

## Цель плана

Создать минимальный, но рабочий каркас backend-сервиса:

- Структура папок `backend/` строго по [.ai-factory/ARCHITECTURE.md](../ARCHITECTURE.md) (domain → application → infrastructure → presentation, плюс core как composition root)
- `pyproject.toml` с зафиксированными версиями ключевых зависимостей (FastAPI, structlog, pydantic-settings, pytest)
- Конфигурация через `pydantic-settings` с поддержкой `.env`
- Структурированное JSON-логирование через `structlog` с `correlation_id` на каждый HTTP-запрос
- Базовые доменные исключения (`AppError`) и RFC 7807 Problem Details exception handlers
- Healthcheck endpoint `GET /api/v1/health` с проверкой liveness и (опционально) подключения к БД
- Композиция FastAPI app в `app/main.py` с подключёнными middleware, routers, exception handlers
- Базовый pytest setup и тесты на healthcheck и загрузку настроек

После плана у нас должен быть `uvicorn app.main:app --reload`, отвечающий 200 на `/api/v1/health` с JSON-логами в stdout.

## Commit Plan

- **Commit 1** (после задач 1-2): `chore(backend): scaffold project structure and pin dependencies`
- **Commit 2** (после задач 3-4): `feat(core): add pydantic-settings config and structlog logging`
- **Commit 3** (после задач 5-6): `feat(core): add shared domain exceptions and RFC 7807 handlers`
- **Commit 4** (после задач 7-8): `feat(api): add healthcheck endpoint and FastAPI app composition`
- **Commit 5** (после задач 9-10): `test(backend): add pytest config and smoke tests`

## Tasks

### Phase 1: Структура проекта и зависимости

- [ ] **Task 1: Создать структуру папок `backend/` по Clean Architecture**
  - **Deliverable:** созданы все директории и файлы-заглушки `__init__.py`:
    - `backend/app/{domain,application,infrastructure,presentation,core}/__init__.py`
    - `backend/app/domain/{radiomap,positioning,attendance,employees,shared}/__init__.py`
    - `backend/app/domain/shared/{exceptions.py,types.py}` (пустые модули с docstring)
    - `backend/app/application/{radiomap,positioning,attendance,employees,ports}/__init__.py`
    - `backend/app/infrastructure/{db,repositories,ml,erp,auth,logging}/__init__.py`
    - `backend/app/infrastructure/db/orm/__init__.py`
    - `backend/app/presentation/{api,schemas}/__init__.py`
    - `backend/app/presentation/api/v1/__init__.py`
    - `backend/tests/{unit,integration,ml}/__init__.py` + `backend/tests/__init__.py`
    - `backend/tests/unit/{domain,application}/__init__.py`
    - `backend/tests/integration/{repositories,api}/__init__.py`
  - **Файлы:** только новые (структура не существует)
  - **LOGGING REQUIREMENTS:** на этом этапе кода нет — логирование настраивается в Task 4
  - **Acceptance:** `tree backend/ -L 4` показывает полную структуру из ARCHITECTURE.md

- [ ] **Task 2: Настроить `pyproject.toml` с зависимостями**
  - **Deliverable:** `backend/pyproject.toml` с зафиксированными версиями
  - **Файлы:** новые — `backend/pyproject.toml`, `backend/.python-version`, `backend/README.md` (минимальный, с командами запуска)
  - **Зависимости (production):** `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `structlog`, `python-json-logger`
  - **Зависимости (dev):** `pytest`, `pytest-asyncio`, `httpx`, `mypy`, `ruff`
  - **Tool config в `pyproject.toml`:** `[tool.ruff]` (line-length 100, target-version py312), `[tool.mypy]` (strict mode для `app/domain` и `app/application`), `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`)
  - **Python:** 3.12+ (зафиксировать в `.python-version`)
  - **LOGGING REQUIREMENTS:** N/A (конфиг)
  - **Acceptance:** `cd backend && pip install -e .[dev]` отрабатывает без ошибок; `ruff check .` и `mypy app/domain` отрабатывают на пустых модулях

### Phase 2: Конфигурация и логирование

- [ ] **Task 3: Реализовать `app/core/config.py` через `pydantic-settings`**
  - **Deliverable:** класс `Settings` с полями:
    - `app_name: str = "svetlyachok-backend"`
    - `environment: Literal["development", "staging", "production"]`
    - `log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"`
    - `log_format: Literal["json", "console"] = "json"`
    - `database_url: PostgresDsn` (read-only, обязательное)
    - `jwt_secret: SecretStr` (обязательное; min length 32)
    - `jwt_algorithm: str = "HS256"`
    - `jwt_access_token_expire_minutes: int = 30`
    - `jwt_refresh_token_expire_days: int = 7`
    - `cors_origins: list[AnyHttpUrl] = []`
  - Класс наследуется от `BaseSettings` с `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)`
  - Cached factory: `@lru_cache` функция `get_settings() -> Settings`
  - **Файлы:** `backend/app/core/config.py` (новый), `backend/.env.example` (с placeholder-значениями), `backend/.env.example` НЕ должен содержать реальных секретов
  - **LOGGING REQUIREMENTS:**
    - В `get_settings()` логировать факт загрузки настроек на DEBUG: `[Settings.load] loaded environment={environment} log_level={log_level}`
    - НЕ логировать `jwt_secret` или `database_url` целиком (только маскированную форму через `repr()` или `***`)
    - Использовать формат: `[Module.function] message {context}`
  - **Acceptance:** `python -c "from app.core.config import get_settings; print(get_settings().model_dump_json())"` выдаёт JSON с настройками; отсутствие `.env` или обязательного поля приводит к понятной ошибке валидации

- [ ] **Task 4: Реализовать `app/core/logging.py` со structlog + correlation_id middleware**
  - **Deliverable:**
    - Функция `configure_logging(settings: Settings) -> None` настраивает structlog с процессорами: `add_log_level`, `TimeStamper(fmt="iso")`, `CallsiteParameterAdder({pathname, lineno})`, finalformatter — JSON или Console в зависимости от `settings.log_format`
    - Bound logger: `get_logger(name: str = __name__) -> structlog.BoundLogger`
    - Middleware `CorrelationIdMiddleware` (ASGI), который:
      - Извлекает `X-Correlation-ID` из header или генерирует UUID4
      - Биндит `correlation_id` в `structlog.contextvars`
      - Возвращает `X-Correlation-ID` в response header
  - **Файлы:** `backend/app/core/logging.py` (новый), `backend/app/presentation/middleware/__init__.py`, `backend/app/presentation/middleware/correlation_id.py`
  - **LOGGING REQUIREMENTS:**
    - На вход middleware: `[CorrelationIdMiddleware.dispatch] start method={method} path={path} correlation_id={cid}` на DEBUG
    - На выход middleware: `[CorrelationIdMiddleware.dispatch] done status={status} duration_ms={ms}` на INFO
    - Все ключи в JSON snake_case
    - При level=DEBUG включается `pathname/lineno` для отладки; в production INFO+ убираются
  - **Acceptance:** запуск `uvicorn` с пустым `app.main` (заглушка) выдаёт JSON-лог при старте; запрос с `X-Correlation-ID: test-123` возвращает тот же header в ответе и логирует `correlation_id=test-123`

### Phase 3: Доменные исключения и обработчики ошибок

- [ ] **Task 5: Реализовать `app/domain/shared/exceptions.py` и `types.py`**
  - **Deliverable:**
    - Базовый класс `AppError(Exception)` с атрибутами `code: str`, `message: str`, `status_code: int = 500`, `details: dict | None = None`
    - Конкретные доменные ошибки: `ValidationError(AppError)` (400), `NotFoundError(AppError)` (404), `ConflictError(AppError)` (409), `UnauthorizedError(AppError)` (401), `ForbiddenError(AppError)` (403)
    - В `types.py` — общие type-aliases: `EmployeeId = NewType("EmployeeId", str)`, `Timestamp = datetime`
  - **Файлы:** `backend/app/domain/shared/exceptions.py`, `backend/app/domain/shared/types.py`
  - **LOGGING REQUIREMENTS:** N/A (sync исключения, логируются в exception handlers Task 6)
  - **Acceptance:** unit-тест проверяет, что `raise ValidationError(code="invalid_email", message="...")` имеет правильный `status_code=400`

- [ ] **Task 6: Реализовать RFC 7807 exception handlers в `app/presentation/exception_handlers.py`**
  - **Deliverable:**
    - Функция `register_exception_handlers(app: FastAPI) -> None`, регистрирующая:
      - Handler для `AppError` → JSON `{type, title, status, detail, instance, code, correlation_id}` (RFC 7807 + расширения)
      - Handler для `RequestValidationError` (Pydantic) → 400 с `validation_errors` массивом
      - Handler для `Exception` (catchall) → 500 с generic сообщением (без stacktrace в response, но stacktrace в логе)
    - `correlation_id` извлекается из `structlog.contextvars` или из header запроса
  - **Файлы:** `backend/app/presentation/exception_handlers.py`, `backend/app/presentation/schemas/errors.py` (Pydantic-схема `ProblemDetailResponse`)
  - **LOGGING REQUIREMENTS:**
    - Для `AppError` — на WARN: `[ExceptionHandler.app_error] code={code} status={status_code} path={path} correlation_id={cid}`
    - Для `RequestValidationError` — на INFO: `[ExceptionHandler.validation] path={path} errors_count={n}`
    - Для catchall `Exception` — на ERROR с `exc_info=True`: `[ExceptionHandler.unhandled] path={path} exc_type={type}`
    - НЕ возвращать stacktrace в response payload; stacktrace только в логе
  - **Acceptance:** при `raise NotFoundError(code="employee_not_found", message="...")` API возвращает 404 с JSON `{"type": "...", "title": "Not Found", "status": 404, "code": "employee_not_found", ...}` и логирует WARN с correlation_id

### Phase 4: HTTP-слой и композиция приложения

- [ ] **Task 7: Реализовать healthcheck endpoint `app/presentation/api/v1/health.py`**
  - **Deliverable:**
    - Pydantic-схема `HealthResponse` с полями `status: Literal["ok", "degraded"]`, `version: str`, `environment: str`, `checks: dict[str, Literal["ok", "fail"]]`
    - Router `health_router = APIRouter(prefix="/health", tags=["health"])`
    - Endpoint `GET /` возвращает `HealthResponse`. На этом этапе только liveness (`{"app": "ok"}` в `checks`). Подключение к БД добавим на следующей вехе вместе с миграциями.
    - Helper-функция (зародыш) `check_database()` — пока возвращает заглушку `"ok"`, помечена `# TODO: подключить SQLAlchemy session check на вехе БД`
  - **Файлы:** `backend/app/presentation/api/v1/health.py`, `backend/app/presentation/schemas/health.py`
  - **LOGGING REQUIREMENTS:**
    - На вход endpoint: `[health.check] start` на DEBUG (нечасто, поэтому DEBUG)
    - На выход: `[health.check] done status={status} checks={checks}` на DEBUG
    - При `status="degraded"` (для будущей расширяемости): WARN с указанием failed checks
  - **Acceptance:** `curl http://localhost:8000/api/v1/health` возвращает `{"status":"ok","version":"0.1.0","environment":"development","checks":{"app":"ok"}}` со статусом 200

- [ ] **Task 8: Композиция FastAPI app в `app/main.py`**
  - **Deliverable:**
    - Функция `create_app() -> FastAPI`:
      1. Загружает `Settings` через `get_settings()`
      2. Вызывает `configure_logging(settings)`
      3. Создаёт `FastAPI(title=settings.app_name, version="0.1.0")`
      4. Подключает middleware: `CorrelationIdMiddleware`, `CORSMiddleware` (с `cors_origins` из настроек)
      5. Подключает routers: `health_router` под префиксом `/api/v1`
      6. Регистрирует exception handlers через `register_exception_handlers(app)`
      7. Логирует `[main.create_app] application initialized version={version} environment={env}` на INFO
      8. Возвращает app
    - Module-level: `app = create_app()` (для `uvicorn app.main:app`)
  - **Файлы:** `backend/app/main.py`
  - **LOGGING REQUIREMENTS:**
    - При старте: `[main.create_app] start environment={env} log_level={log_level}` (DEBUG)
    - После сборки: `[main.create_app] ready routers=[...] middleware=[...]` (INFO)
    - При ошибке инициализации: `[main.create_app] failed exc_type={type}` (ERROR с `exc_info=True`) и rethrow — fail fast при старте
  - **Acceptance:** `cd backend && uvicorn app.main:app --port 8000` запускается без ошибок; первый лог-строкой выдаёт JSON `[main.create_app] ready ...`; `curl /api/v1/health` отрабатывает

### Phase 5: Тесты и верификация

- [ ] **Task 9: Pytest configuration + базовые fixtures**
  - **Deliverable:**
    - `backend/tests/conftest.py` с fixtures:
      - `settings_overrides()` — позволяет переопределить настройки в тестах через `monkeypatch.setenv`
      - `client(app)` — `httpx.AsyncClient` для интеграционных тестов FastAPI
      - `app(settings)` — fixture, создающий FastAPI app с тестовыми настройками
    - `backend/tests/unit/conftest.py`, `backend/tests/integration/conftest.py` (пустые с заглушкой импортов из родительского)
    - `backend/.env.test` (тестовое окружение с фиктивными значениями: `DATABASE_URL=postgresql://test/test`, `JWT_SECRET=test_secret_at_least_32_chars_long`, и т.д.)
  - **Файлы:** `backend/tests/conftest.py`, `backend/tests/unit/conftest.py`, `backend/tests/integration/conftest.py`, `backend/.env.test`
  - **LOGGING REQUIREMENTS:**
    - Caplog/structlog capture в conftest для возможности проверки логов в тестах: `pytest_structlog` или ручной `structlog.testing.LogCapture`
    - Все тесты должны иметь возможность assertить лог-строки
  - **Acceptance:** `cd backend && pytest --collect-only` показывает все собранные тесты без ошибок импорта

- [ ] **Task 10: Smoke-тесты на healthcheck endpoint и загрузку настроек**
  - **Deliverable:**
    - `backend/tests/unit/core/test_config.py`:
      - test: загрузка `Settings` с минимальными переменными окружения проходит
      - test: пропуск обязательного поля (например `DATABASE_URL`) кидает `ValidationError`
      - test: маскирование `jwt_secret` в `repr(settings)`
    - `backend/tests/unit/domain/test_shared_exceptions.py`:
      - test: `ValidationError` имеет `status_code=400`
      - test: `NotFoundError` имеет `status_code=404`
    - `backend/tests/integration/api/test_health.py`:
      - test: `GET /api/v1/health` возвращает 200 и `{"status":"ok"}`
      - test: response содержит `X-Correlation-ID` header (echo от middleware)
      - test: переданный `X-Correlation-ID` отражается в response
      - test: лог содержит запись `[health.check]` с `correlation_id`
  - **Файлы:** `backend/tests/unit/core/test_config.py`, `backend/tests/unit/domain/test_shared_exceptions.py`, `backend/tests/integration/api/test_health.py`
  - **LOGGING REQUIREMENTS:** N/A (тесты)
  - **Acceptance:** `cd backend && pytest -v` проходит без падений; coverage хотя бы 70% на `app/core/`, `app/presentation/`, `app/domain/shared/`

## Документационный чекпоинт (после Task 10)

В конце реализации `/aif-implement` остановится и предложит запустить `/aif-docs`. Документация должна включать:

- Раздел README в `backend/README.md`: команды установки, запуска, тестов, миграций
- Описание архитектуры на стартовой странице backend (ссылка на `.ai-factory/ARCHITECTURE.md`)
- Описание переменных окружения (с пометкой обязательных)

## Открытые вопросы

- Подключение к БД проверяется в `health.check_database()` как заглушка. На следующей вехе («База данных и миграции») заменим на реальный `SELECT 1`.
- Конкретный набор `cors_origins` для production уточнится позже — пока пустой список (CORS отключён в dev).
- Хеширование паролей `bcrypt` будет добавлено на вехе «Аутентификация».
