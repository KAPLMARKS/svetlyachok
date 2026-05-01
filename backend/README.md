# Backend АИС «Светлячок»

Серверная часть системы автоматизированного учёта посещаемости на базе Wi-Fi RSSI fingerprinting.

## Стек

- Python 3.12+
- FastAPI (async REST API)
- pydantic-settings, structlog
- pytest, ruff, mypy

## Установка

```bash
cd backend
python -m venv .venv
source .venv/bin/activate     # Linux/macOS
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
```

## Конфигурация

Скопируйте `.env.example` в `.env` и заполните обязательные поля (`DATABASE_URL`, `JWT_SECRET`).

```bash
cp .env.example .env
```

## Команды

| Действие | Команда |
|----------|---------|
| Запуск dev-сервера | `uvicorn app.main:app --reload --port 8000` |
| Тесты (все) | `pytest -v` |
| Тесты (только unit) | `pytest -v -m unit` |
| Coverage | `pytest --cov=app --cov-report=term-missing` |
| Линтер | `ruff check .` |
| Авто-форматирование | `ruff format .` |
| Type check | `mypy app` |

## Эндпоинты

| Метод | Путь | Назначение |
|-------|------|-----------|
| `GET` | `/api/v1/health` | Healthcheck (liveness + БД проверка) |

Полный OpenAPI: http://localhost:8000/docs (Swagger UI), http://localhost:8000/redoc.

## Архитектура

Clean Architecture: domain → application → infrastructure → presentation.
Подробное описание — в `../.ai-factory/ARCHITECTURE.md`.

## Структура проекта

```
backend/
├── app/
│   ├── domain/           # Чистая бизнес-логика, без зависимостей
│   ├── application/      # Use cases
│   ├── infrastructure/   # SQLAlchemy, scikit-learn, JWT, 1С
│   ├── presentation/     # FastAPI routers, схемы, middleware
│   ├── core/             # Композиция (DI, settings, logging)
│   └── main.py           # Точка входа
├── alembic/              # Миграции БД
├── tests/
│   ├── unit/             # Тесты domain и application слоёв
│   ├── integration/      # Тесты репозиториев и API
│   └── ml/               # Метрологические тесты
└── pyproject.toml
```
