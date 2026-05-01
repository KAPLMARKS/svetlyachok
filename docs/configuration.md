[← API Reference](api.md) · [Back to README](../README.md)

# Конфигурация

Все настройки backend задаются через переменные окружения или `.env`-файл. Обработка — через `pydantic-settings`.

## Файлы конфигурации

| Файл | Назначение | Коммитим? |
|------|-----------|-----------|
| `backend/.env.example` | Шаблон с placeholder-значениями | ✅ Да |
| `backend/.env` | Локальные настройки (содержит секреты) | ❌ Нет (в `.gitignore`) |
| `backend/.env.test` | Тестовое окружение для pytest | ✅ Да (только фиктивные значения) |
| `backend/pyproject.toml` | Метаданные пакета, конфиги ruff/mypy/pytest | ✅ Да |

## Переменные окружения

### Application

| Переменная | Тип | По умолчанию | Описание |
|-----------|-----|--------------|----------|
| `APP_NAME` | string | `svetlyachok-backend` | Имя приложения для FastAPI title и логов |
| `ENVIRONMENT` | enum | `development` | Одно из: `development`, `staging`, `production` |

### Logging

| Переменная | Тип | По умолчанию | Описание |
|-----------|-----|--------------|----------|
| `LOG_LEVEL` | enum | `DEBUG` | `DEBUG` / `INFO` / `WARNING` / `ERROR`. В production используйте `INFO` |
| `LOG_FORMAT` | enum | `json` | `json` (production-friendly) или `console` (читаемый в dev) |

**Поведение по уровням:**

- `DEBUG` — детальные логи + callsite info (pathname/lineno) для отладки
- `INFO` — ключевые события (запросы, ошибки доменной валидации)
- `WARNING` — нештатные ситуации, низкая уверенность ML, validation errors
- `ERROR` — необработанные исключения, провал внешних сервисов

### Database

| Переменная | Тип | Обязательная? | Описание |
|-----------|-----|---------------|----------|
| `DATABASE_URL` | PostgresDsn | ✅ Да | Async DSN PostgreSQL: `postgresql+asyncpg://user:pass@host:5432/db` |

**Пример для local development:**

```
DATABASE_URL=postgresql+asyncpg://svetlyachok:dev_password@localhost:5432/svetlyachok
```

**Подводный камень:** обязательно используйте `+asyncpg` драйвер (не дефолтный `psycopg2`), иначе SQLAlchemy не сможет работать асинхронно.

### JWT / Security

| Переменная | Тип | По умолчанию | Описание |
|-----------|-----|--------------|----------|
| `JWT_SECRET` | SecretStr | (обязательная) | Секрет для подписи JWT. **Минимум 32 символа** (валидируется в pydantic) |
| `JWT_ALGORITHM` | string | `HS256` | Алгоритм подписи JWT. HS256/HS384/HS512 для symmetric |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | int (1..1440) | `30` | Время жизни access-токена в минутах |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | int (1..90) | `7` | Время жизни refresh-токена в днях |

**Генерация надёжного секрета:**

```bash
# Linux / macOS
openssl rand -base64 48

# Windows PowerShell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
```

**Важно:** при ротации `JWT_SECRET` все существующие токены становятся невалидными. Планируйте ротацию вместе с rolling-deploy.

### CORS

| Переменная | Тип | По умолчанию | Описание |
|-----------|-----|--------------|----------|
| `CORS_ORIGINS` | list[AnyHttpUrl] | `[]` | Список разрешённых origin для веб-панели. Пустой список = CORS отключён |

**Формат значения** (JSON-массив строк):

```
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

**Production:** используйте только конкретные origin'ы (никогда `*` в production), и не разрешайте credentials с wildcard.

## Маскирование секретов в логах

`JWT_SECRET` объявлен как `SecretStr` — pydantic автоматически маскирует значение в `repr()` и `model_dump_json()`. В логах будет `**********` вместо реального значения. Это проверяется в unit-тестах (`tests/unit/core/test_config.py::test_jwt_secret_is_masked_in_repr`).

## Загрузка настроек

В коде:

```python
from app.core.config import get_settings

settings = get_settings()  # кешируется через @lru_cache
print(settings.environment)
print(settings.database_url)
print(settings.jwt_secret.get_secret_value())  # явный unmask
```

`get_settings()` загружает `.env` один раз при первом вызове и кеширует результат. В тестах кеш очищается автоматически (см. `tests/conftest.py`).

## Валидация при старте

Настройки валидируются при создании `Settings()`. Невалидные значения приводят к `ValidationError` и приложение **не запускается** (fail fast):

- Отсутствие `DATABASE_URL` → `ValidationError`
- `JWT_SECRET` короче 32 символов → `ValidationError`
- Невалидный `LOG_LEVEL` (не из enum) → `ValidationError`
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` < 1 или > 1440 → `ValidationError`

## Изменение настроек в runtime

Изменения переменных окружения **во время работы** приложения **не подхватываются** автоматически из-за `@lru_cache`. Чтобы перечитать настройки:

```python
from app.core.config import get_settings
get_settings.cache_clear()  # сброс кеша
new_settings = get_settings()  # повторная загрузка
```

В production это бывает нужно при горячей ротации секретов. Обычно проще перезапустить приложение.

## See Also

- [Начало работы](getting-started.md) — установка и первый запуск
- [API Reference](api.md) — endpoints и формат ошибок
