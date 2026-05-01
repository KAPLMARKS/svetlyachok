<!-- handoff:task:8e75cb8d-19e5-4b20-8dc9-9678ab4c0468 -->

# Implementation Plan: Аутентификация (JWT)

Branch: feature/backend-auth-jwt-8e75cb
Created: 2026-05-01

## Settings

- Testing: yes (pytest для всех слоёв; unit для криптографии и use cases, integration для эндпоинтов с реальной БД)
- Logging: verbose (structlog с DEBUG-уровнем; LOG_LEVEL контролирует продакшен)
- Docs: yes (обязательный чекпоинт документации в `/aif-implement` финале)

## Roadmap Linkage

Milestone: "Аутентификация (JWT)"
Rationale: Этот план реализует четвёртую веху роадмапа — слой аутентификации на основе JSON Web Tokens с защитой эндпоинтов через FastAPI Depends. Без него все последующие вехи (управление сотрудниками/зонами, приём радиоотпечатков, учёт рабочего времени, web-панель и mobile-приложение) не смогут безопасно работать с защищёнными API.

## Цель плана

Реализовать аутентификацию по схеме «email + пароль → JWT access/refresh токены» с защитой роутов через FastAPI Depends:

- bcrypt-хеширование паролей (work factor 12)
- Кодирование/декодирование JWT через PyJWT (HS256, секрет из Settings)
- Два эндпоинта: `POST /api/v1/auth/login` (email + password → access + refresh tokens), `POST /api/v1/auth/refresh` (refresh token → новая пара токенов)
- FastAPI dependency `get_current_user` для inject'а аутентифицированного `Employee` в защищённые роуты
- FastAPI dependency `require_role(Role.ADMIN)` для роль-based авторизации (admin-only эндпоинты появятся на следующих вехах CRUD)
- Rate limiting на `/auth/login` и `/auth/refresh` через slowapi (5 запросов/минута/IP) — защита от брутфорса
- Демо-эндпоинт `GET /api/v1/me` (защищённый, возвращает текущего пользователя) — заменит TODO-плейсхолдер на реальное использование `get_current_user`
- Обновлённый seed-скрипт с реальными bcrypt-хешами для admin/employee

После плана у нас должно быть:

- `curl -X POST /api/v1/auth/login -d '{"email":"admin@svetlyachok.local","password":"..."}'` → 200 + `{"access_token":"...","refresh_token":"...","token_type":"bearer","expires_in":1800}`
- `curl -X POST /api/v1/auth/refresh -d '{"refresh_token":"..."}'` → новая пара токенов
- `curl -H "Authorization: Bearer ${ACCESS}" /api/v1/me` → 200 + JSON с email/role/full_name
- Без токена `/me` → 401 с RFC 7807 Problem Details
- 6 неудачных попыток `/login` за минуту с одного IP → 429 Too Many Requests

## Commit Plan

- **Commit 1** (после задач 1-3): `chore(auth): добавить bcrypt + PyJWT + slowapi, реализовать password hasher и JWT provider`
- **Commit 2** (после задач 4-5): `feat(employees): доменные сущности и SQLAlchemy-репозиторий`
- **Commit 3** (после задач 6-7): `feat(auth): use cases login и refresh tokens`
- **Commit 4** (после задач 8-9): `feat(api): эндпоинты POST /api/v1/auth/login и /auth/refresh`
- **Commit 5** (после задач 10-12): `feat(api): rate limiting на /auth, current_user dependency, подключение router в main`
- **Commit 6** (после задач 13-14): `feat(api): защищённый GET /api/v1/me + bcrypt-хеши в seed`
- **Commit 7** (после задач 15-16): `test(auth): unit-тесты криптографии и интеграционные тесты эндпоинтов`
- **Commit 8** (после задачи 17): `docs: руководство по аутентификации в backend/README.md`

## Tasks

### Phase 1: Криптографические примитивы и зависимости

- [x] **Task 1: Добавить bcrypt, PyJWT, slowapi в `pyproject.toml`**
  - **Deliverable:** обновлённый `backend/pyproject.toml`
  - **Production dependencies (добавить):**
    - `bcrypt>=4.2.0,<5.0.0` (нативный, без passlib — passlib имеет известные проблемы совместимости с bcrypt 4+)
    - `pyjwt[crypto]>=2.9.0,<3.0.0` (`[crypto]` extra включает cryptography для будущего перехода на RS256/EdDSA)
    - `slowapi>=0.1.9,<0.2.0` (rate limiting через limits-библиотеку, легковесно интегрируется с FastAPI)
  - **Файлы:** `backend/pyproject.toml` (модификация)
  - **LOGGING REQUIREMENTS:** N/A (конфиг)
  - **Acceptance:** `pip install -e .[dev]` отрабатывает; `python -c "import bcrypt, jwt, slowapi; print(bcrypt.__version__, jwt.__version__)"` выдаёт корректные версии

- [x] **Task 2: Реализовать `app/infrastructure/auth/password_hasher.py` (bcrypt)**
  - **Deliverable:**
    - Класс `BcryptPasswordHasher` (без зависимостей от passlib):
      - `def hash(plain: str) -> str` — `bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12))`, возвращает строку (utf-8 декодированный хеш)
      - `def verify(plain: str, hashed: str) -> bool` — `bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))`; ловит `ValueError` (битый hash) и возвращает False
      - **Constant-time** через bcrypt.checkpw — никаких ручных сравнений
    - **Work factor 12** — стандарт OWASP 2024, ≈ 250 ms/попытка на современных CPU; защита от брутфорса
    - Опциональный `Protocol PasswordHasher` в `app/domain/employees/services.py` — use cases работают через Protocol, не через конкретную реализацию (DI совместимость)
  - **Файлы:** `backend/app/infrastructure/auth/password_hasher.py` (новый), `backend/app/domain/employees/services.py` (новый, Protocol)
  - **LOGGING REQUIREMENTS:**
    - `hash`: на DEBUG `[auth.password_hasher.hash] hashed length={n} rounds=12` (без plain-text!)
    - `verify`: на DEBUG `[auth.password_hasher.verify] result={ok|fail}` (без plain-text и hash полностью)
    - НИКОГДА не логировать пароль в открытом виде или полный hash
  - **Acceptance:** unit-тест: `hasher.verify("secret", hasher.hash("secret"))` → True; `verify("wrong", ...)` → False; `verify("any", "broken-hash")` → False (ValueError caught)

- [x] **Task 3: Реализовать `app/infrastructure/auth/jwt_provider.py` (encode/decode)**
  - **Deliverable:**
    - Класс `JwtProvider`:
      - `__init__(self, settings: Settings)` — берёт `jwt_secret`, `jwt_algorithm`, expire-таймауты
      - `encode_access_token(subject: str, role: str) -> tuple[str, datetime]` — возвращает токен и datetime истечения; payload: `{sub, role, type: "access", iat, exp, jti}`
      - `encode_refresh_token(subject: str) -> tuple[str, datetime]` — payload: `{sub, type: "refresh", iat, exp, jti}` (без role — refresh не нужен для авторизации, только для обмена)
      - `decode(token: str, expected_type: Literal["access", "refresh"]) -> JwtClaims` — валидирует подпись, exp, тип; кидает `domain.shared.exceptions.UnauthorizedError(code="invalid_token"|"expired_token"|"wrong_token_type")`
    - Dataclass `JwtClaims` (frozen): `sub: str`, `role: str | None`, `type: str`, `iat: datetime`, `exp: datetime`, `jti: str`
    - `subject` = `Employee.id` (строка), не email — id стабильнее при смене email
    - `jti` (JWT ID) — `uuid4().hex`, заложен на будущее для blacklist'а отозванных токенов (ставим, но проверяем revocation позже)
  - **Файлы:** `backend/app/infrastructure/auth/jwt_provider.py` (новый), `backend/app/infrastructure/auth/__init__.py` (модификация — экспорт)
  - **LOGGING REQUIREMENTS:**
    - На encode: DEBUG `[auth.jwt.encode] type={access|refresh} subject={sub} expires_at={iso}` (без самого токена)
    - На decode успех: DEBUG `[auth.jwt.decode] ok type={t} subject={sub}`
    - На decode ошибку: WARN `[auth.jwt.decode] fail reason={expired|invalid_signature|wrong_type|malformed} exc_type={...}` (без токена в логе)
    - НИКОГДА не логировать сам токен (`access_token` или `refresh_token` целиком)
  - **Acceptance:** unit-тесты:
    - encode → decode round-trip даёт исходный subject/role
    - decode чужого токена с другим секретом → `UnauthorizedError(code="invalid_token")`
    - decode access-токена при `expected_type="refresh"` → `UnauthorizedError(code="wrong_token_type")`
    - decode истёкшего токена → `UnauthorizedError(code="expired_token")`
    - decode мусора (`"not.a.jwt"`) → `UnauthorizedError(code="invalid_token")`

### Phase 2: Domain слой для employees

- [x] **Task 4: Доменные сущности и Protocol для employees**
  - **Deliverable:**
    - `app/domain/employees/entities.py`:
      - `@dataclass(frozen=True) class Employee`: `id: int`, `email: str`, `full_name: str`, `role: Role`, `hashed_password: str`, `is_active: bool`, `schedule_start: time | None`, `schedule_end: time | None`
      - `class Role(str, Enum)`: `ADMIN = "admin"`, `EMPLOYEE = "employee"` (зеркально ORM-enum'у; domain не импортирует SQLAlchemy)
      - Метод `Employee.is_authenticated_admin() -> bool` — для удобства проверок в use cases (опционально)
    - `app/domain/employees/value_objects.py`:
      - `EmployeeId = NewType("EmployeeId", int)` — типизирующий alias
    - `app/domain/employees/repositories.py`:
      - `class EmployeeRepository(Protocol)`:
        - `async def get_by_id(self, employee_id: int) -> Employee | None`
        - `async def get_by_email(self, email: str) -> Employee | None`
  - **Файлы:** `backend/app/domain/employees/entities.py`, `backend/app/domain/employees/value_objects.py`, `backend/app/domain/employees/repositories.py` (все новые)
  - **LOGGING REQUIREMENTS:** N/A (pure data classes + Protocol)
  - **Acceptance:** `from app.domain.employees.entities import Employee, Role` импортируется без побочных импортов SQLAlchemy/FastAPI; `Role.ADMIN.value == "admin"`

- [x] **Task 5: SQLAlchemy-реализация `EmployeeRepository`**
  - **Deliverable:**
    - `app/infrastructure/repositories/employees_repository.py`:
      - Класс `SqlAlchemyEmployeeRepository`, реализует Protocol из Task 4
      - Конструктор: `__init__(self, session: AsyncSession)`
      - `get_by_id` и `get_by_email` через `select(EmployeeORM).where(...)`
      - Маппер ORM → domain: метод `_to_domain(orm: EmployeeORM) -> Employee` (приватный)
    - **Не возвращать ORM-модель наружу** — только domain entity (правило Clean Architecture)
  - **Файлы:** `backend/app/infrastructure/repositories/employees_repository.py` (новый), `backend/app/infrastructure/repositories/__init__.py` (модификация — экспорт)
  - **LOGGING REQUIREMENTS:**
    - DEBUG `[employees.repo.get_by_id] start id={id}` / `done found={bool}`
    - DEBUG `[employees.repo.get_by_email] start email={email}` (email не PII в нашем контексте, но в логе видим — отметим в открытых вопросах) `done found={bool}`
  - **Acceptance:** `pytest tests/integration/repositories/test_employees.py` — после seed возвращает Employee с корректными полями; для несуществующего email → None

### Phase 3: Application — use cases

- [x] **Task 6: Use case `application/employees/authenticate.py` (LoginUseCase)**
  - **Deliverable:**
    - `@dataclass(frozen=True) class LoginCommand`: `email: str`, `password: str`
    - `@dataclass(frozen=True) class TokenPair`: `access_token: str`, `refresh_token: str`, `expires_in: int` (секунды до истечения access; нужно клиентам для proactive-refresh)
    - `class LoginUseCase`:
      - `__init__(self, repo: EmployeeRepository, hasher: PasswordHasher, jwt: JwtProvider)`
      - `async def execute(self, cmd: LoginCommand) -> TokenPair`
      - Алгоритм:
        1. `repo.get_by_email(email)` → `Employee | None`
        2. Если `None` или `not is_active` или `not hasher.verify(password, hashed)` → `UnauthorizedError(code="invalid_credentials", message="Неверный email или пароль")`
        3. **Дамми-хеш для timing safety:** если `Employee` не найден, всё равно вызываем `hasher.verify(password, DUMMY_HASH)` — иначе по времени ответа можно отличить «нет пользователя» от «есть, но пароль неверный» (timing attack на enumerate)
        4. Сгенерировать access (с role) и refresh (без role)
        5. Вернуть `TokenPair(access, refresh, expires_in=settings.jwt_access_token_expire_minutes * 60)`
    - **DUMMY_HASH** — сгенерирован один раз, лежит как module-level константа: `bcrypt.hashpw(b"dummy_for_timing_attack_protection", bcrypt.gensalt(rounds=12))`
  - **Файлы:** `backend/app/application/employees/authenticate.py` (новый)
  - **LOGGING REQUIREMENTS:**
    - DEBUG на старте: `[auth.login.execute] start email={email}` (без password!)
    - INFO на успехе: `[auth.login.execute] success employee_id={id} role={role}`
    - WARN на неудаче: `[auth.login.execute] fail reason={user_not_found|inactive|wrong_password} email={email}` (различаем причины в логах для оператора, но в response — единое 401 чтобы не палить enumerate)
  - **Acceptance:** unit-тест с in-memory fake-repo + fake-hasher: успех при правильных данных, fail при любой из трёх причин; время ответа на «нет такого email» ≈ время на «неверный пароль» (тест measure'ит min/max через `time.perf_counter`, ratio в пределах 1.5x)

- [x] **Task 7: Use case `application/employees/refresh_tokens.py`**
  - **Deliverable:**
    - `@dataclass(frozen=True) class RefreshCommand`: `refresh_token: str`
    - `class RefreshTokensUseCase`:
      - `__init__(self, repo: EmployeeRepository, jwt: JwtProvider)`
      - `async def execute(self, cmd: RefreshCommand) -> TokenPair`
      - Алгоритм:
        1. `jwt.decode(refresh_token, expected_type="refresh")` → `JwtClaims` (или поднимется UnauthorizedError из jwt_provider)
        2. `repo.get_by_id(int(claims.sub))` → `Employee` (если None или not is_active → UnauthorizedError(code="user_disabled"))
        3. Сгенерировать новую пару токенов (без token rotation на этой вехе — refresh остаётся прежним до истечения; rotation добавим вместе с blacklist'ом jti, отметим в открытых вопросах)
        4. Вернуть `TokenPair(new_access, same_refresh_or_new, expires_in=...)` — для пилота отдаём ту же refresh, чтобы упростить mobile-клиент
  - **Файлы:** `backend/app/application/employees/refresh_tokens.py` (новый)
  - **LOGGING REQUIREMENTS:**
    - DEBUG `[auth.refresh.execute] start subject={sub}` (sub берём из claims, без самого токена)
    - INFO `[auth.refresh.execute] success employee_id={id}`
    - WARN `[auth.refresh.execute] fail reason={invalid_token|expired|user_disabled|user_not_found}`
  - **Acceptance:** unit-тест: при валидном refresh выдаёт новую пару; при истёкшем → UnauthorizedError(code="expired_token"); при отозванном пользователе → UnauthorizedError(code="user_disabled")

### Phase 4: Presentation — endpoints

- [x] **Task 8: Pydantic схемы `presentation/schemas/auth.py`**
  - **Deliverable:**
    - `class LoginRequest(BaseModel)`: `email: EmailStr`, `password: SecretStr` (использует `pydantic.SecretStr` — автоматическая маска в repr/JSON; в Field указать `min_length=8, max_length=128`)
    - `class RefreshRequest(BaseModel)`: `refresh_token: str` (Field min_length=10)
    - `class TokenResponse(BaseModel)`: `access_token: str`, `refresh_token: str`, `token_type: Literal["bearer"] = "bearer"`, `expires_in: int`
    - `class CurrentUserResponse(BaseModel)`: `id: int`, `email: EmailStr`, `full_name: str`, `role: str`, `is_active: bool` (без `hashed_password`!)
    - `model_config` для всех — `ConfigDict(extra="forbid")` чтобы клиенты не могли пробросить лишних полей
  - **Файлы:** `backend/app/presentation/schemas/auth.py` (новый)
  - **LOGGING REQUIREMENTS:** N/A (DTO без логики)
  - **Acceptance:** unit-тест: `LoginRequest(email="admin@x.com", password="abc12345")` парсится; `password.get_secret_value()` возвращает строку; `LoginRequest(...).model_dump()` маскирует password как `'**********'`

- [x] **Task 9: Эндпоинты `presentation/api/v1/auth.py` (POST /login, /refresh)**
  - **Deliverable:**
    - `router = APIRouter(prefix="/auth", tags=["auth"])`
    - `POST /login`:
      - Принимает `LoginRequest`, dependency `LoginUseCase = Depends(get_login_use_case)`
      - Возвращает `TokenResponse`, status `200`
      - При `UnauthorizedError` use case'а — handler из presentation/exception_handlers.py отдаёт RFC 7807 401
    - `POST /refresh`:
      - Принимает `RefreshRequest`, dependency `RefreshTokensUseCase`
      - Возвращает `TokenResponse`
    - DI-функции в `presentation/dependencies.py`:
      - `get_password_hasher() -> PasswordHasher` (singleton — `BcryptPasswordHasher()` — ничего не кэширует, можно создавать каждый раз, но ради DI оставим в functools.lru_cache)
      - `get_jwt_provider(settings = Depends(get_settings)) -> JwtProvider`
      - `get_employee_repository(session = Depends(get_session)) -> EmployeeRepository`
      - `get_login_use_case(...)` и `get_refresh_use_case(...)` композируют выше
  - **Файлы:** `backend/app/presentation/api/v1/auth.py` (новый), `backend/app/presentation/dependencies.py` (модификация)
  - **LOGGING REQUIREMENTS:**
    - На input: DEBUG `[auth.endpoint.login] start email={email}` (без password!)
    - Use cases уже логируют успех/неудачу — handler не дублирует
    - На refresh: DEBUG `[auth.endpoint.refresh] start` (без refresh_token!)
  - **Acceptance:** integration-тесты (Task 16) — POST /login с верными credentials → 200 + TokenResponse, неверный пароль → 401 + RFC 7807

- [x] **Task 10: Rate limiting через slowapi на /auth-эндпоинты**
  - **Deliverable:**
    - `app/presentation/middleware/rate_limit.py`:
      - `limiter = Limiter(key_func=get_remote_address)` — ключ по IP клиента (через `request.client.host`, с поддержкой `X-Forwarded-For` за proxy)
      - Конфигурация дефолтных лимитов через Settings: добавить поля `auth_login_rate_limit: str = "5/minute"`, `auth_refresh_rate_limit: str = "10/minute"`
    - В `auth.py` декораторы:
      - `@limiter.limit(settings.auth_login_rate_limit)` на `POST /login`
      - `@limiter.limit(settings.auth_refresh_rate_limit)` на `POST /refresh`
    - В `main.py`:
      - `app.state.limiter = limiter`
      - `app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)` — handler возвращает RFC 7807 429 с `code="rate_limit_exceeded"`, retry-after header
    - Если за proxy/балансировщиком — `X-Forwarded-For` обработка через `slowapi.util.get_ipaddr` (требует ENV var `TRUST_PROXY=true`); по умолчанию используем `request.client.host`
  - **Файлы:** `backend/app/presentation/middleware/rate_limit.py` (новый), `backend/app/presentation/api/v1/auth.py` (модификация — добавить декораторы), `backend/app/main.py` (модификация — register limiter и handler), `backend/app/core/config.py` (модификация — поля rate limit)
  - **LOGGING REQUIREMENTS:**
    - На rate limit hit: WARN `[auth.rate_limit] exceeded path={path} ip={ip} limit={limit}` (через handler)
  - **Acceptance:** integration-тест: 6 запросов на /login с одного IP за < 1 минуту → 6-й возвращает 429 + JSON RFC 7807 + `Retry-After` header

- [x] **Task 11: Dependency `get_current_user` и `require_role` в `presentation/dependencies.py`**
  - **Deliverable:**
    - `oauth2_scheme = HTTPBearer(auto_error=False)` — НЕ `OAuth2PasswordBearer` (мы не используем `/token`-форму, а Bearer заголовок)
    - `async def get_current_user(credentials = Depends(oauth2_scheme), jwt = Depends(get_jwt_provider), repo = Depends(get_employee_repository)) -> Employee`:
      - Если нет credentials → `UnauthorizedError(code="missing_token")`
      - `jwt.decode(credentials.credentials, expected_type="access")` → claims или UnauthorizedError из decode
      - `repo.get_by_id(int(claims.sub))` → `Employee` (либо UnauthorizedError если не найден или not is_active)
      - Возвращает Employee
    - `def require_role(*allowed_roles: Role) -> Callable`:
      - Возвращает callable-dependency, которая принимает `user = Depends(get_current_user)` и проверяет `user.role in allowed_roles`
      - При неудаче → `ForbiddenError(code="insufficient_role", details={"required": [...], "actual": "..."})`
      - Использование: `@router.get("/admin/things", dependencies=[Depends(require_role(Role.ADMIN))])`
  - **Файлы:** `backend/app/presentation/dependencies.py` (модификация)
  - **LOGGING REQUIREMENTS:**
    - DEBUG `[auth.deps.current_user] resolved employee_id={id} role={role}`
    - WARN `[auth.deps.current_user] fail reason={missing|invalid|disabled}`
    - WARN `[auth.deps.require_role] denied employee_id={id} required={req} actual={act}`
  - **Acceptance:** unit-тест: `get_current_user` с моком `HTTPAuthorizationCredentials("invalid")` → UnauthorizedError; `require_role(Role.ADMIN)` для employee-пользователя → ForbiddenError

- [x] **Task 12: Подключить auth_router и rate limiter в `main.py`**
  - **Deliverable:**
    - В `main.py` `create_app`:
      - `from app.presentation.api.v1.auth import router as auth_router`
      - `from app.presentation.middleware.rate_limit import limiter`
      - `app.state.limiter = limiter`
      - `app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)`
      - `app.include_router(auth_router, prefix="/api/v1")`
    - Лог `[main.create_app] ready` пополнить routers списком: `["/api/v1/health", "/api/v1/auth"]`
  - **Файлы:** `backend/app/main.py` (модификация)
  - **LOGGING REQUIREMENTS:** N/A (фабрика, логи там уже есть)
  - **Acceptance:** `uvicorn app.main:app` стартует без ошибок; `curl /docs` показывает Swagger с группой `auth` (POST /login, POST /refresh)

### Phase 5: Защищённый эндпоинт + обновление seed

- [x] **Task 13: Защищённый `GET /api/v1/me` (демо-эндпоинт)**
  - **Deliverable:**
    - `app/presentation/api/v1/me.py`:
      - `router = APIRouter(prefix="/me", tags=["users"])`
      - `GET /` → `CurrentUserResponse`, dependency `Depends(get_current_user)` → возвращает Employee → маппится в DTO
    - Подключить в `main.py`: `app.include_router(me_router, prefix="/api/v1")`
  - **Файлы:** `backend/app/presentation/api/v1/me.py` (новый), `backend/app/main.py` (модификация — include router)
  - **LOGGING REQUIREMENTS:**
    - DEBUG `[me.get] employee_id={id}` (current_user уже резолвлен зависимостью)
  - **Acceptance:** integration-тест:
    - `GET /me` без токена → 401 + RFC 7807 `code="missing_token"`
    - `GET /me` с валидным access → 200 + JSON Employee без hashed_password
    - `GET /me` с истёкшим токеном → 401 + `code="expired_token"`

- [x] **Task 14: Обновить seed-скрипт — реальные bcrypt-хеши**
  - **Deliverable:**
    - В `scripts/seed.py` заменить `_PLACEHOLDER_PASSWORD` на реальные хеши через `BcryptPasswordHasher`:
      - admin: пароль `admin12345` (для dev — задокументирован в seed.py docstring и в README, что в production такие пароли недопустимы)
      - employee: пароль `employee12345`
    - Хеши генерируются на лету при запуске seed-скрипта (не хранить хеши в коде — генерить bcrypt'ом каждый раз, всё равно идёт ON CONFLICT DO NOTHING; повторный seed просто пропустит)
    - Удалить `# noqa: S105` — больше не нужен, литерала пароля в коде нет
  - **Файлы:** `backend/scripts/seed.py` (модификация)
  - **LOGGING REQUIREMENTS:** N/A (используем уже существующие логи seed-скрипта)
  - **Acceptance:** на свежей БД `python scripts/seed.py` создаёт admin/employee; `POST /api/v1/auth/login` с этими паролями возвращает 200 + TokenPair

### Phase 6: Тесты

- [x] **Task 15: Unit-тесты криптографии и use cases**
  - **Deliverable:**
    - `tests/unit/infrastructure/auth/test_password_hasher.py`:
      - hash + verify round-trip
      - verify пустой строки → False (без падения)
      - verify сломанного hash → False
      - hash дважды одной строки → разные hash'и (gensalt)
    - `tests/unit/infrastructure/auth/test_jwt_provider.py`:
      - encode → decode round-trip (subject, role совпадают)
      - decode с другим секретом → UnauthorizedError(invalid_token)
      - decode access как refresh → UnauthorizedError(wrong_token_type)
      - decode истёкшего → UnauthorizedError(expired_token); поддельность проверяется через freezegun или manual `expire_at = past`
      - decode мусора → UnauthorizedError(invalid_token)
    - `tests/unit/application/test_authenticate_use_case.py`:
      - in-memory FakeEmployeeRepository, FakePasswordHasher, FakeJwtProvider
      - success → TokenPair
      - wrong password → UnauthorizedError(invalid_credentials)
      - inactive user → UnauthorizedError(invalid_credentials) — те же 401, чтобы не палить enumerate
      - non-existent user → UnauthorizedError(invalid_credentials); время ответа примерно равно успешному (timing safety тест)
    - `tests/unit/application/test_refresh_use_case.py`:
      - success
      - non-existent subject → UnauthorizedError(user_not_found)
      - inactive subject → UnauthorizedError(user_disabled)
  - **Файлы:** новые директории/файлы под `tests/unit/infrastructure/auth/` и `tests/unit/application/`
  - **LOGGING REQUIREMENTS:** N/A (тесты)
  - **Acceptance:** `pytest tests/unit/infrastructure/auth/ tests/unit/application/ -v` зелёный; coverage для `app/infrastructure/auth/` ≥ 90%, для `app/application/employees/` ≥ 85%

- [x] **Task 16: Integration-тесты эндпоинтов /auth и /me**
  - **Deliverable:**
    - `tests/integration/api/test_auth.py`:
      - `test_login_success`: после seed POST /login с email + password → 200 + TokenResponse; access декодируется и содержит правильный subject/role
      - `test_login_wrong_password`: → 401 + JSON `{"type": "...", "code": "invalid_credentials"}`
      - `test_login_unknown_email`: → 401 + same code (enumerate-safety)
      - `test_login_validation_error`: невалидный email → 400 RFC 7807 (validation_errors массив)
      - `test_login_rate_limit`: 6 запросов подряд → 6-й 429 + Retry-After header
      - `test_refresh_success`: получаем refresh из login, шлём в /refresh → новая пара
      - `test_refresh_invalid`: рандомная строка → 401 + `code="invalid_token"`
      - `test_refresh_with_access_token`: подменяем access как refresh → 401 + `code="wrong_token_type"`
    - `tests/integration/api/test_me.py`:
      - `test_me_without_token`: → 401 + `code="missing_token"`
      - `test_me_with_valid_token`: → 200 + JSON без hashed_password
      - `test_me_with_invalid_token`: → 401 + `code="invalid_token"`
    - Используют существующие fixtures `client_with_db`, `db_sessionmaker` из conftest (БД с миграциями + seed для тестового пользователя в фикстуре)
    - Новая fixture `seeded_employee` — создаёт Employee с известным паролем через ORM напрямую (чтобы не зависеть от seed-скрипта в каждом тесте)
  - **Файлы:** `backend/tests/integration/api/test_auth.py`, `backend/tests/integration/api/test_me.py` (новые)
  - **LOGGING REQUIREMENTS:** N/A (тесты)
  - **Acceptance:** `pytest tests/integration/api/test_auth.py tests/integration/api/test_me.py -v` зелёный (требует Docker / TEST_DATABASE_URL); rate-limit-тест выполняется детерминированно (slowapi storage перезапускается на каждый тест через fixture)

### Phase 7: Документация

- [x] **Task 17: Обновить `backend/README.md` — раздел «Аутентификация»**
  - **Deliverable:**
    - Раздел «Аутентификация»:
      - Описание схемы (email + password → access/refresh JWT, access 30 min, refresh 7 days)
      - Команды получения токена (`curl -X POST /api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"admin@svetlyachok.local","password":"admin12345"}'`)
      - Использование Bearer-токена (`-H "Authorization: Bearer <access>"`)
      - Refresh flow (`/api/v1/auth/refresh`)
      - Rate limiting (5 req/min /login, 10 req/min /refresh — конфигурируется через `AUTH_LOGIN_RATE_LIMIT`/`AUTH_REFRESH_RATE_LIMIT` в .env)
      - **Безопасность**: bcrypt rounds 12, JWT HS256, секрет из env (минимум 32 символа), не использовать seed-пароли в production, ротировать `JWT_SECRET` при необходимости (это инвалидирует все активные токены)
    - Обновить раздел «Эндпоинты» — добавить `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `GET /api/v1/me`
    - Обновить раздел «Переменные окружения» — упомянуть `AUTH_LOGIN_RATE_LIMIT`, `AUTH_REFRESH_RATE_LIMIT`
    - Обновить `backend/.env.example` синхронно
  - **Файлы:** `backend/README.md` (модификация), `backend/.env.example` (модификация)
  - **LOGGING REQUIREMENTS:** N/A (документация)
  - **Acceptance:** новый раздел читается без перехода в исходники; команды из примеров копипастятся и работают на dev-окружении

## Документационный чекпоинт (после Task 17)

В конце реализации `/aif-implement` остановится и предложит запустить `/aif-docs`. Документация должна включать:

- Раздел «Аутентификация» в `backend/README.md` с командами и описанием flow
- Описание ролей (ADMIN/EMPLOYEE) и матрицы доступа к эндпоинтам (заполнится по мере появления защищённых endpoint'ов на следующих вехах)
- Безопасностные ограничения (bcrypt rounds, JWT TTL, rate limits) и переменные окружения

## Открытые вопросы

- **Token rotation на refresh**: на этой вехе refresh не ротируется (для упрощения mobile-кэша). Если на этапе полевых испытаний обнаружим повторное использование украденного refresh — добавим rotation + blacklist'ование `jti` через Redis или таблицу `revoked_tokens`.
- **PII в логах**: логируем email и employee_id. Для пилота приемлемо (закрытая инсталляция в одном вузе, доступ к логам — администратор). Для production — заменить email на хеш или employee_id-only; вынести в правило `.ai-factory/rules/security.md` на вехе production-готовности.
- **Refresh token storage**: пока возвращаем клиенту в JSON. Mobile-приложение должно хранить refresh в Android Keystore / iOS Keychain. Web-панель будет использовать HttpOnly Secure cookies (с CSRF-защитой). Это отметим в плане соответствующих вех (mobile/web).
- **Password reset flow**: для пилота не делаем (`admin` создаёт пользователей с временным паролем, передаёт лично). Появится при необходимости — нужен будет email-провайдер (на вехе production).
- **Multi-factor authentication**: не предусмотрено. Пилот в закрытом контуре вуза.
- **Logout-эндпоинт**: тривиально для access (клиент сам удаляет токен), но без blacklist'а jti revoke для refresh не получится. Рассмотрим вместе с rotation на следующих итерациях.
- **Audit log аутентификации**: success/fail логи пишутся через structlog. Если потребуется отдельный audit-журнал в БД (для соответствия 152-ФЗ или внутренних security-policy) — добавим таблицу `auth_audit` через миграцию.
