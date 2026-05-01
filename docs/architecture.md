[← Начало работы](getting-started.md) · [Back to README](../README.md) · [API Reference →](api.md)

# Архитектура

Краткий обзор архитектурных решений проекта АИС «Светлячок». Полное описание с примерами кода, правилами зависимостей и паттернами — в [.ai-factory/ARCHITECTURE.md](../.ai-factory/ARCHITECTURE.md).

## Высокоуровневая структура

Проект состоит из трёх независимых модулей, общающихся через REST API:

```
┌──────────────┐    HTTPS     ┌─────────────────┐
│  Mobile      │◄────────────►│                 │
│  (Flutter)   │              │                 │
└──────────────┘              │     Backend     │
                              │   (FastAPI)     │
┌──────────────┐    HTTPS     │                 │
│  Web Admin   │◄────────────►│                 │
│  (React)     │              └────────┬────────┘
└──────────────┘                       │
                                       ▼
                              ┌─────────────────┐
                              │   PostgreSQL    │
                              └─────────────────┘
```

## Backend: Clean Architecture

Backend использует Clean Architecture (Robert C. Martin) с четырьмя слоями. Зависимости направлены строго **внутрь**: внешние слои знают о внутренних, но не наоборот.

### Слои

| Слой | Назначение | Может зависеть от |
|------|-----------|-------------------|
| `domain/` | Чистая бизнес-логика, entities, value objects, Protocol-контракты | — (только stdlib) |
| `application/` | Use cases, оркестрация, ports | `domain` |
| `infrastructure/` | SQLAlchemy, scikit-learn, JWT, 1С-клиент | `domain`, `application` |
| `presentation/` | FastAPI routers, Pydantic-схемы, middleware | `application`, `core` |
| `core/` | Composition root, settings, logging | всё остальное |

### Структура папок

```
backend/app/
├── domain/
│   ├── radiomap/         # Fingerprint, RSSIVector, BSSID
│   ├── positioning/      # PositionEstimate, ZoneClassification, PositionClassifier
│   ├── attendance/       # AttendanceLog, WorkSession, Lateness
│   ├── employees/        # Employee, Role
│   └── shared/           # AppError, NewType-обёртки
├── application/
│   ├── radiomap/         # use cases приёма отпечатков и калибровки
│   ├── positioning/      # use cases классификации
│   ├── attendance/       # use cases расчёта рабочего времени
│   ├── employees/        # use cases авторизации
│   └── ports/            # контракты внешних сервисов (1C client, notifications)
├── infrastructure/
│   ├── db/               # SQLAlchemy session, ORM-модели
│   ├── repositories/     # реализации Protocols из domain
│   ├── ml/               # WKNN, Random Forest, метрики
│   ├── erp/              # 1С-клиент
│   ├── auth/             # JWT, bcrypt
│   └── logging/          # structlog setup
├── presentation/
│   ├── api/v1/           # FastAPI routers
│   ├── schemas/          # Pydantic request/response schemas
│   ├── middleware/       # CorrelationIdMiddleware
│   └── exception_handlers.py  # RFC 7807 handlers
├── core/
│   ├── config.py         # pydantic-settings
│   ├── logging.py        # structlog config
│   └── container.py      # DI composition root
└── main.py               # FastAPI app entry point
```

## Правила зависимостей

### Разрешено

- `presentation` → `application`, `core`
- `application` → `domain`
- `infrastructure` → `domain`, `application` (реализует Protocols)

### Запрещено

- ❌ `domain` → `application` / `infrastructure` / `presentation` (домен ничего не знает о внешнем мире)
- ❌ `application` → `infrastructure` напрямую (только через Protocols)
- ❌ Импорт `sqlalchemy` или `fastapi` в `app/domain/`
- ❌ Возврат ORM-моделей из use cases (только Pydantic-схемы или dataclass)

## Domain как Protocol-first

Доменный слой объявляет интерфейсы через `typing.Protocol`. Реализация — в `infrastructure/`. Это позволяет:

- Тестировать use cases с in-memory fake-репозиториями (без БД)
- Подменить scikit-learn на TensorFlow без касания доменной логики
- Сравнивать алгоритмы (WKNN vs Random Forest) на одном test-сете — оба реализуют один Protocol

Пример:

```python
# domain/positioning/classifiers.py
from typing import Protocol

class PositionClassifier(Protocol):
    def classify(self, observation, calibration_set) -> ZoneClassification: ...

# infrastructure/ml/wknn_classifier.py
class WknnClassifier:  # неявно реализует Protocol
    def classify(self, observation, calibration_set):
        # scikit-learn KNeighborsClassifier(weights="distance")
        ...
```

Подробности — в [skill `wifi-rssi-wknn`](../.claude/skills/wifi-rssi-wknn/SKILL.md).

## Mobile (Flutter, Android-only)

Mobile использует слоистую архитектуру согласно установленному скиллу `flutter-apply-architecture-best-practices`:

```
mobile/lib/
├── data/                 # API клиент (Dio), Wi-Fi сервис, sqflite кэш
├── domain/               # Модели и репозитории (абстракции)
├── features/             # auth, scanning, calibration
├── shared/               # общие виджеты и утилиты
└── main.dart
```

**Важное ограничение:** мобильное приложение Android-only. iOS не поддерживается из-за невозможности доступа к API сканирования соседних Wi-Fi сетей с RSSI без специального entitlement Apple. Это методологическое ограничение зафиксировано в [.ai-factory/DESCRIPTION.md](../.ai-factory/DESCRIPTION.md).

## Web admin panel (React + Vite + TypeScript)

Web использует feature-based структуру согласно скиллу `vercel-react-best-practices`:

```
web/src/
├── api/                  # API клиент с типами из OpenAPI
├── features/             # auth, radiomap, attendance, employees
├── components/           # переиспользуемые компоненты
├── hooks/                # общие хуки (TanStack Query, Zustand)
└── routes/               # React Router конфигурация
```

## Контракт между клиентами и backend

- Backend публикует OpenAPI-спецификацию по `/openapi.json`
- Клиенты генерируют типы из неё:
  - Web: `openapi-typescript` → TypeScript types
  - Mobile: `build_runner` + `json_serializable` → Dart classes
- Версионирование через URL-префикс `/api/v1/`, `/api/v2/` при breaking changes

## See Also

- [API Reference](api.md) — текущие endpoints и их форматы
- [Конфигурация](configuration.md) — переменные окружения
- [.ai-factory/ARCHITECTURE.md](../.ai-factory/ARCHITECTURE.md) — детальные правила, примеры кода, anti-patterns
