[Back to README](../README.md) · [Архитектура →](architecture.md)

# Начало работы

Инструкции по установке, конфигурации и первому запуску бэкенда АИС «Светлячок».

На текущем этапе реализован backend-каркас с healthcheck endpoint. Mobile (Flutter) и Web (React) модули будут добавлены на следующих вехах — см. [.ai-factory/ROADMAP.md](../.ai-factory/ROADMAP.md).

## Требования

| Компонент | Версия | Назначение |
|-----------|--------|------------|
| Python | 3.12+ | Backend runtime |
| pip | 24+ | Установка зависимостей |
| PostgreSQL | 16+ | Production-БД (опционально на этапе scaffold) |
| Git | 2.40+ | Контроль версий |

Опциональные инструменты:
- Docker Desktop — для локального запуска PostgreSQL без установки на host
- VS Code или PyCharm — для разработки

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/KAPLMARKS/svetlyachok.git
cd svetlyachok
```

### 2. Виртуальное окружение Python

```bash
cd backend
python -m venv .venv
```

Активация:

| Платформа | Команда |
|-----------|---------|
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (CMD/Git Bash) | `.venv\Scripts\activate` |
| Linux / macOS | `source .venv/bin/activate` |

### 3. Установка зависимостей

```bash
pip install -e ".[dev]"
```

Это установит:
- Production: `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `structlog`
- Dev: `pytest`, `pytest-asyncio`, `httpx`, `mypy`, `ruff`

### 4. Конфигурация окружения

```bash
cp .env.example .env
```

Откройте `.env` и заполните обязательные поля:

- `DATABASE_URL` — строка подключения к PostgreSQL (для разработки можно использовать SQLite-эквивалент или временно фиктивный DSN, поскольку БД пока не используется)
- `JWT_SECRET` — секрет для подписи JWT, минимум **32 символа**

Сгенерировать надёжный секрет:

```bash
# macOS / Linux
openssl rand -base64 48

# Windows PowerShell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
```

Полное описание переменных окружения — в [docs/configuration.md](configuration.md).

## Первый запуск

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Ожидаемый вывод (формат JSON-логов):

```json
{"event": "[main.create_app] start", "level": "debug", ...}
{"event": "[main.create_app] ready", "level": "info", "version": "0.1.0", ...}
INFO:     Uvicorn running on http://127.0.0.1:8000
```

## Проверка работы

Healthcheck endpoint:

```bash
curl http://localhost:8000/api/v1/health
```

Ожидаемый ответ:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "checks": {
    "app": "ok",
    "database": "ok"
  }
}
```

Интерактивная документация API:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Запуск тестов

```bash
cd backend
pytest -v                                    # Все тесты
pytest -v -m unit                            # Только unit
pytest -v -m integration                     # Только integration
pytest --cov=app --cov-report=term-missing   # С покрытием
```

На текущей вехе включено 16 smoke-тестов:
- 8 тестов доменных исключений
- 4 теста загрузки настроек
- 4 теста healthcheck endpoint

## Линтер и проверка типов

```bash
cd backend
ruff check .                  # Линтер
ruff format .                 # Авто-форматирование
mypy app                      # Проверка типов (строгая для domain/application)
```

## Следующие шаги

После того как scaffold запускается:

1. Изучите [архитектуру проекта](architecture.md) — Clean Architecture, слои, правила зависимостей
2. Изучите [API Reference](api.md) — текущие endpoints
3. Изучите [конфигурацию](configuration.md) — переменные окружения и их роль

## See Also

- [Архитектура](architecture.md) — структура слоёв и правила зависимостей
- [Конфигурация](configuration.md) — переменные окружения
