<!-- handoff:task:f81e4d01-d6bc-4ed9-9b5b-46157e8ec9d2 -->

# Implementation Plan: Управление сотрудниками и зонами

Branch: feature/backend-employees-zones-crud-f81e4d
Created: 2026-05-01

## Settings

- Testing: yes (unit для use cases, integration для эндпоинтов)
- Logging: verbose (structlog с DEBUG)
- Docs: yes (mandatory checkpoint)

## Roadmap Linkage

Milestone: "Управление сотрудниками и зонами"
Rationale: Пятая веха роадмапа. Обеспечивает админскую инфраструктуру для всех клиентов (web/mobile) — без CRUD employees/zones невозможно ни заводить новых пользователей, ни конфигурировать радиокарту, ни запускать ML-калибровку на следующих вехах.

## Цель плана

Реализовать REST API для управления сущностями `Employee` и `Zone` в admin-only режиме (с ограниченными self-операциями для employee):

**Employees:**
- `POST /api/v1/employees` (admin) — создать сотрудника со временным паролем
- `GET /api/v1/employees` (admin) — список с пагинацией и фильтрами `role`, `is_active`
- `GET /api/v1/employees/{id}` (admin или self) — детали
- `PATCH /api/v1/employees/{id}` (admin полностью; self только `full_name`) — обновить
- `POST /api/v1/employees/{id}/password` (admin сброс или self смена с проверкой старого) — сменить пароль
- `POST /api/v1/employees/{id}/deactivate` (admin) — soft-delete через `is_active=false`
- `POST /api/v1/employees/{id}/activate` (admin) — реактивация

**Zones:**
- `POST /api/v1/zones` (admin) — создать зону
- `GET /api/v1/zones` (любой авторизованный — клиентам нужен список для UI)
- `GET /api/v1/zones/{id}` (любой авторизованный)
- `PATCH /api/v1/zones/{id}` (admin)
- `DELETE /api/v1/zones/{id}` (admin) — hard-delete; если есть `attendance_logs` (FK RESTRICT) → 409 Conflict с понятным сообщением

После плана:
- Web-панель сможет полноценно управлять пользователями и зонами
- Mobile сможет получать список зон для отображения на карте
- На следующих вехах (приём fingerprints, attendance_logs) появятся работающие зависимости

## Commit Plan

- **Commit 1** (Tasks 1-2): `chore(domain): расширить EmployeeRepository, добавить domain zones`
- **Commit 2** (Tasks 3-4): `feat(infrastructure): SQLAlchemy-репозитории employees расширен, zones новый`
- **Commit 3** (Tasks 5-9): `feat(employees): use cases CRUD сотрудников`
- **Commit 4** (Tasks 10-12): `feat(zones): use cases CRUD зон`
- **Commit 5** (Tasks 13-14): `feat(api): Pydantic-схемы employees и zones`
- **Commit 6** (Tasks 15-17): `feat(api): эндпоинты employees, zones и подключение в main`
- **Commit 7** (Tasks 18-19): `test(unit): unit-тесты use cases employees и zones`
- **Commit 8** (Tasks 20-21): `test(integration): интеграционные тесты эндпоинтов`
- **Commit 9** (Task 22): `docs: руководство по CRUD employees и zones`

## Tasks

### Phase 1: Domain слой

- [x] **Task 1: Расширить `EmployeeRepository` Protocol**
  - **Deliverable:** в `app/domain/employees/repositories.py` добавить методы:
    - `async def list(*, role: Role | None, is_active: bool | None, limit: int, offset: int) -> list[Employee]`
    - `async def count(*, role: Role | None, is_active: bool | None) -> int` (для пагинации — total)
    - `async def add(employee: Employee) -> Employee` (возвращает с заполненным id)
    - `async def update(employee: Employee) -> Employee` (по id)
  - Сохраняем существующие `get_by_id` и `get_by_email`
  - **LOGGING REQUIREMENTS:** N/A (Protocol)
  - **Acceptance:** `EmployeeRepository.__abstractmethods__` (если бы была абстракция) включал бы все 6; mypy strict проходит на использования

- [x] **Task 2: Domain модуль `zones`**
  - **Deliverable:**
    - `app/domain/zones/entities.py`: frozen dataclass `Zone(id, name, type, description, display_color)` + enum `ZoneType` (значения зеркалят ORM); enum `ZoneType` — единый источник правды (re-export из `app.domain.zones.entities` в presentation/dependencies)
    - `app/domain/zones/repositories.py`: Protocol `ZoneRepository` с `get_by_id`, `get_by_name`, `list(limit, offset, type_filter)`, `count(type_filter)`, `add(zone)`, `update(zone)`, `delete_by_id(zone_id) -> bool` (true если удалили, false если есть зависимости)
    - `app/domain/zones/__init__.py` (пустой)
  - **LOGGING REQUIREMENTS:** N/A
  - **Acceptance:** `from app.domain.zones.entities import Zone, ZoneType` без побочных импортов

### Phase 2: Infrastructure слой

- [x] **Task 3: Расширить `SqlAlchemyEmployeeRepository`**
  - **Deliverable:** в `app/infrastructure/repositories/employees_repository.py`:
    - `list` через `select(EmployeeORM).where(filters).order_by(EmployeeORM.id).limit(limit).offset(offset)` с конъюнкцией фильтров
    - `count` через `select(func.count()).select_from(EmployeeORM).where(...)`
    - `add` — `session.add(orm); await session.flush(); return self._to_domain(orm)` (id заполнится после flush благодаря Identity)
    - `update` — `select` по id → обновить поля → flush → return domain. Если не найден — `NotFoundError(code="employee_not_found")`
    - При ConflictError (unique violation на email при создании дубля) поднимать `ConflictError(code="employee_email_taken")`
  - **Файлы:** `backend/app/infrastructure/repositories/employees_repository.py` (модификация)
  - **LOGGING REQUIREMENTS:**
    - DEBUG на каждый метод: `[employees.repo.<method>] start ...` / `done ...`
    - WARN на ConflictError/NotFoundError с указанием поля/id
  - **Acceptance:** integration-тест на repository с testcontainer Postgres покрывает все методы

- [x] **Task 4: Реализовать `SqlAlchemyZoneRepository`**
  - **Deliverable:** новый файл `app/infrastructure/repositories/zones_repository.py`. ORM `Zone` уже есть. Все методы аналогично employees-repo.
    - `delete_by_id`: пытаемся `session.delete()` + `flush()`; ловим `IntegrityError` (FK constraint от `attendance_logs.zone_id` ondelete=RESTRICT) и поднимаем `ConflictError(code="zone_in_use", details={"reason": "attendance_logs_exist"})`
  - Маппер ORM → domain `_to_domain` — приватный
  - Зарегистрировать через `app/infrastructure/repositories/__init__.py` (экспорт)
  - **LOGGING REQUIREMENTS:** аналогично employees-repo
  - **Acceptance:** integration-тест: создать зону → попытаться удалить (ОК) → создать ещё одну, добавить attendance_log → попытаться удалить → ConflictError

### Phase 3: Application — use cases employees

- [x] **Task 5: `CreateEmployeeUseCase`**
  - **Deliverable:** `app/application/employees/create_employee.py`:
    - `CreateEmployeeCommand(email, full_name, role, initial_password, schedule_start, schedule_end)`
    - Алгоритм: проверить, что email не занят (`get_by_email` → если есть → `ConflictError(employee_email_taken)`); хешировать пароль; `repo.add(Employee(...))`; вернуть domain Employee
    - Валидация роли: только `Role.ADMIN` или `Role.EMPLOYEE` (Pydantic уже фильтрует, но domain тоже не должен принять мусор — конструктор `Employee` использует `Role`-enum)
  - **Файлы:** новый
  - **LOGGING REQUIREMENTS:**
    - INFO на успехе: `[employees.create.execute] success employee_id={id} email={email} role={role}`
    - WARN на конфликт: `[employees.create.execute] fail reason=email_taken email={email}`
  - **Acceptance:** unit с in-memory fake — happy path возвращает Employee с id; повторный create с тем же email → ConflictError

- [x] **Task 6: `ListEmployeesUseCase`**
  - **Deliverable:** `app/application/employees/list_employees.py`:
    - `ListEmployeesQuery(role: Role | None = None, is_active: bool | None = None, limit: int = 50, offset: int = 0)`
    - `Page[Employee]` (frozen dataclass с `items: list[Employee]`, `total: int`, `limit: int`, `offset: int`)
    - Лимиты: `1 <= limit <= 200` валидируется в presentation, в use case — assert как inv
  - **Файлы:** новый
  - **LOGGING REQUIREMENTS:**
    - DEBUG: `[employees.list.execute] start filters={...} limit={n} offset={m}`
    - DEBUG: `[employees.list.execute] done total={t} returned={k}`
  - **Acceptance:** unit с fake repo возвращает корректную Page

- [x] **Task 7: `UpdateEmployeeUseCase`**
  - **Deliverable:** `app/application/employees/update_employee.py`:
    - `UpdateEmployeeCommand(employee_id, *, full_name=None, role=None, schedule_start=None, schedule_end=None)` — все поля опциональны (PATCH-семантика)
    - Алгоритм: get_by_id → если None → NotFoundError; применить только non-None поля; repo.update; вернуть Employee
  - **Файлы:** новый
  - **LOGGING REQUIREMENTS:** INFO на успехе с employee_id и changed fields, WARN на NotFoundError
  - **Acceptance:** unit — partial-update меняет только переданные поля, остальные остаются

- [x] **Task 8: `ChangePasswordUseCase`**
  - **Deliverable:** `app/application/employees/change_password.py`:
    - `ChangePasswordCommand(employee_id, *, new_password, old_password=None, is_admin_reset=False)`
    - Алгоритм:
      - `is_admin_reset=True` → не проверяем old (вызывает только admin через эндпоинт)
      - `is_admin_reset=False` → требуем `old_password`; делаем `hasher.verify(old, employee.hashed_password)` → False → `UnauthorizedError(code="wrong_old_password")`
      - В обоих случаях: `hasher.hash(new) → repo.update`
    - Min length проверяется в Pydantic-схеме (8 символов)
  - **Файлы:** новый
  - **LOGGING REQUIREMENTS:** INFO `success employee_id={id} mode={admin_reset|self_change}`, WARN на wrong_old_password
  - **Acceptance:** unit — admin-режим без old, self-режим с правильным old, self-режим с неверным old → UnauthorizedError

- [x] **Task 9: `DeactivateEmployeeUseCase` + `ActivateEmployeeUseCase`**
  - **Deliverable:** `app/application/employees/deactivate_employee.py` (один файл, два use case'а):
    - Меняют `is_active` flag через `repo.update(employee.with_is_active(...))` (нужен helper `Employee.with_is_active(value: bool) -> Employee` — frozen dataclass replace)
    - Защита: admin не может деактивировать сам себя (передаём `current_user_id` в команду; если совпадает → `ForbiddenError(code="cannot_deactivate_self")`)
  - **Файлы:** новый
  - **LOGGING REQUIREMENTS:** INFO `success employee_id={id} is_active={bool}`
  - **Acceptance:** unit — deactivate чужой OK, deactivate себя → ForbiddenError; реактивация работает

### Phase 4: Application — use cases zones

- [x] **Task 10: `CreateZoneUseCase`**
  - **Deliverable:** `app/application/zones/create_zone.py`:
    - `CreateZoneCommand(name, type, description=None, display_color=None)`
    - Проверка уникальности по name (get_by_name → если есть → `ConflictError(zone_name_taken)`)
    - HEX-формат `display_color` валидируется в Pydantic-схеме
  - **Файлы:** новый, плюс `app/application/zones/__init__.py` (новый пустой)
  - **LOGGING REQUIREMENTS:** INFO success/conflict
  - **Acceptance:** unit с fake — create OK, дубль name → ConflictError

- [x] **Task 11: `ListZonesUseCase` + `GetZoneUseCase`**
  - **Deliverable:** `app/application/zones/list_zones.py`:
    - `ListZonesQuery(type_filter: ZoneType | None = None, limit=50, offset=0)`
    - `Page[Zone]`
    - `get_zone(zone_id) -> Zone | None` — простая обёртка для эндпоинта (или встроить в endpoint?), оставлю отдельным use case'ом для consistency
  - **Файлы:** новый
  - **Acceptance:** unit

- [x] **Task 12: `UpdateZoneUseCase` + `DeleteZoneUseCase`**
  - **Deliverable:** `app/application/zones/update_zone.py` и `delete_zone.py`:
    - Update — partial-update, по id
    - Delete — `repo.delete_by_id` → если False (есть зависимости) → `ConflictError(zone_in_use)`
  - **Файлы:** новые
  - **LOGGING REQUIREMENTS:** INFO success, WARN на conflict
  - **Acceptance:** unit

### Phase 5: Presentation — schemas + endpoints

- [x] **Task 13: Pydantic-схемы employees**
  - **Deliverable:** `app/presentation/schemas/employees.py`:
    - `EmployeeCreateRequest(email: EmailStr, full_name: str (min 1, max 255), role: Role, initial_password: SecretStr (min 8, max 128), schedule_start: time | None, schedule_end: time | None)`
    - `EmployeeUpdateRequest` (все поля Optional, для PATCH)
    - `ChangePasswordRequest(new_password: SecretStr, old_password: SecretStr | None = None)` (для self передают old, для admin reset не передают)
    - `EmployeeResponse(id, email, full_name, role, is_active, schedule_start, schedule_end)` (без `hashed_password`!)
    - `EmployeesPageResponse(items: list[EmployeeResponse], total, limit, offset)`
    - Все с `extra="forbid"`
  - **Файлы:** новый
  - **Acceptance:** валидация работает, schema_dump не палит password

- [x] **Task 14: Pydantic-схемы zones**
  - **Deliverable:** `app/presentation/schemas/zones.py`:
    - `ZoneCreateRequest(name (1-100), type: ZoneType, description: str | None, display_color: str | None (HEX через regex pattern `^#[0-9A-Fa-f]{6}$` в Field))`
    - `ZoneUpdateRequest` (все опциональны)
    - `ZoneResponse(id, name, type, description, display_color)`
    - `ZonesPageResponse`
  - **Файлы:** новый
  - **Acceptance:** инвалидный HEX → 400 Pydantic validation

- [x] **Task 15: Endpoints `/api/v1/employees`**
  - **Deliverable:** `app/presentation/api/v1/employees.py`:
    - `POST /` — `Depends(require_role(Role.ADMIN))` → CreateEmployeeUseCase → 201 + EmployeeResponse
    - `GET /` — `Depends(require_role(Role.ADMIN))` → ListEmployeesUseCase + query params (`role`, `is_active`, `limit`, `offset`)
    - `GET /{id}` — `Depends(get_current_user)` → если current.role != ADMIN и current.id != id → ForbiddenError; → EmployeeResponse
    - `PATCH /{id}` — admin полное обновление; self только full_name (валидация в endpoint: если current не admin и кто-то прислал role/schedule_* — ForbiddenError)
    - `POST /{id}/password` — admin без old_password (передаёт `is_admin_reset=True`); self только своя запись + old_password обязателен; иначе ForbiddenError
    - `POST /{id}/deactivate` — admin (передаёт current.id для anti-self-lock)
    - `POST /{id}/activate` — admin
  - DI-функции для всех use cases в `presentation/dependencies.py` (новые)
  - **Файлы:** новый, `presentation/dependencies.py` (модификация)
  - **LOGGING REQUIREMENTS:** DEBUG на старте каждого endpoint'а с указанием employee_id
  - **Acceptance:** integration-тесты в Task 20

- [x] **Task 16: Endpoints `/api/v1/zones`**
  - **Deliverable:** `app/presentation/api/v1/zones.py`:
    - `POST /` — admin → CreateZoneUseCase → 201
    - `GET /` — любой авторизованный (Depends(get_current_user)) → ListZonesUseCase
    - `GET /{id}` — любой авторизованный
    - `PATCH /{id}` — admin
    - `DELETE /{id}` — admin → 204 No Content; ConflictError → 409
  - **Файлы:** новый
  - **Acceptance:** integration-тесты в Task 21

- [x] **Task 17: Подключить routers в `main.py` + DI dependencies**
  - **Deliverable:**
    - `presentation/dependencies.py`: новые `get_create_employee_use_case`, `get_list_employees_use_case`, `get_update_employee_use_case`, `get_change_password_use_case`, `get_deactivate_employee_use_case`, `get_activate_employee_use_case`, `get_create_zone_use_case`, `get_list_zones_use_case`, `get_update_zone_use_case`, `get_delete_zone_use_case`, `get_zone_repository` (singleton-фабрика по сессии)
    - `main.py`: include `employees_router`, `zones_router`; обновить лог `[main.create_app] ready` со списком новых routers
  - **Файлы:** `presentation/dependencies.py` (модификация), `main.py` (модификация)
  - **Acceptance:** `uvicorn` стартует, `/docs` показывает группы Employees и Zones

### Phase 6: Тесты

- [x] **Task 18: Unit-тесты use cases employees**
  - **Deliverable:** `tests/unit/application/test_create_employee.py`, `test_list_employees.py`, `test_update_employee.py`, `test_change_password.py`, `test_deactivate_employee.py`
  - In-memory `FakeEmployeeRepository` (расширенная: с `_storage: dict[int, Employee]` и автоинкрементом `_next_id`)
  - Покрытие: успех, конфликт, NotFoundError, ForbiddenError для self-deactivate
  - **Acceptance:** ≥ 90% coverage для `app/application/employees/`

- [x] **Task 19: Unit-тесты use cases zones**
  - **Deliverable:** `tests/unit/application/test_create_zone.py`, `test_list_zones.py`, `test_update_zone.py`, `test_delete_zone.py`
  - **Acceptance:** ≥ 90% coverage для `app/application/zones/`

- [x] **Task 20: Integration-тесты эндпоинтов /employees**
  - **Deliverable:** `tests/integration/api/test_employees.py`:
    - Fixtures: `seeded_admin` (через прямой db_engine commit с известным паролем), `admin_token` (login → access), `employee_token` (login self-employee)
    - Тесты:
      - POST /employees от admin → 201
      - POST /employees от employee → 403
      - POST /employees с дублем email → 409
      - GET /employees от admin → список с пагинацией
      - GET /employees от employee → 403
      - GET /employees/{id} self → 200
      - GET /employees/{id} чужого employee → 403
      - PATCH /employees/{id} admin меняет role → OK
      - PATCH /employees/{id} self меняет full_name → OK
      - PATCH /employees/{id} self пытается изменить role → 403
      - POST /employees/{id}/password admin без old → 200
      - POST /employees/{id}/password self с правильным old → 200; с неверным old → 401
      - POST /employees/{my_id}/deactivate (admin сам себя) → 403
      - POST /employees/{other_id}/deactivate (admin) → 200, потом этот пользователь не может login (если активна проверка is_active в LoginUseCase — да, она там есть)
  - Сброс slowapi state autouse fixture (как в test_auth)
  - **Acceptance:** все assertions проходят при наличии Docker

- [x] **Task 21: Integration-тесты эндпоинтов /zones**
  - **Deliverable:** `tests/integration/api/test_zones.py`:
    - Тесты:
      - POST /zones admin → 201
      - POST /zones employee → 403
      - GET /zones любой авторизованный → список
      - PATCH /zones/{id} admin → OK
      - DELETE /zones/{id} без зависимостей → 204
      - DELETE /zones/{id} с attendance_log → 409 + code=zone_in_use (создаём запись через прямой ORM)
      - POST /zones с инвалидным HEX → 422
  - **Acceptance:** проходит при наличии Docker

### Phase 7: Документация

- [x] **Task 22: Обновить `backend/README.md`**
  - **Deliverable:**
    - Раздел «Управление сотрудниками» — описание ролей, эндпоинтов с curl-примерами для каждого основного сценария (создание admin'ом, смена пароля self/admin, deactivate)
    - Раздел «Управление зонами» — типы зон, эндпоинты, поведение DELETE при наличии зависимостей
    - Обновить таблицу «Эндпоинты» — добавить все новые
  - **Файлы:** `backend/README.md` (модификация)
  - **Acceptance:** примеры copy-pasteable, читаются без переключения в исходники

## Документационный чекпоинт (после Task 22)

В `/aif-implement` финале остановка и предложение `/aif-docs`. Документация должна включать:
- Раздел «CRUD employees» с матрицей доступа (admin/self/employee) по эндпоинтам
- Раздел «CRUD zones» с описанием поведения DELETE при FK RESTRICT (409 zone_in_use)
- Обновлённый список эндпоинтов и переменных окружения (если появятся)

## Открытые вопросы

- **Hard delete employees**: пока не делаем — soft через `is_active=false` (PII-данные у нас минимальные, GDPR-стиль удаление можно добавить позже как отдельную задачу с явным флагом и аудитом).
- **Audit log изменений**: пока не делаем — все мутации видны в structlog. Если понадобится формальный журнал (152-ФЗ или внутренний security policy) — добавим таблицу `audit_log` с миграцией.
- **Принудительная смена пароля при первом входе**: не предусмотрено. Admin создаёт со временным паролем и сообщает его сотруднику лично. Force-password-change-on-first-login можно добавить флаг `password_changed_at` в БД через миграцию.
- **Validation password strength**: пока только `min_length=8` — без проверок на сложность (заглавные/цифры/спец-символы). Для пилота приемлемо; на production-готовности добавим [zxcvbn](https://github.com/dwolfhub/zxcvbn-python) или аналог.
- **Pagination cursor vs offset**: используем `limit/offset`. Для пилота с ≤ 200 employees приемлемо. Если таблица вырастет — мигрируем на cursor-based.
- **Soft-delete для zones**: пока hard-delete с проверкой FK. Если на полевых испытаниях понадобится «архивация» зон без потери истории — добавим `archived_at` через миграцию.
