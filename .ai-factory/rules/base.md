# Базовые правила проекта АИС «Светлячок»

> Соглашения по стилю и структуре кода для всех модулей проекта. Сгенерированы автоматически при настройке `/aif`. Расширяйте через `/aif-rules`.

Проект содержит три независимых модуля (`backend/`, `mobile/`, `web/`) с разными стеками. Правила сгруппированы по модулям.

## Общие правила

### Идентификаторы и язык

- Имена файлов, функций, переменных, классов, констант — **только английский язык** (latin1)
- Комментарии в коде, docstrings, README, документация — **русский язык**
- CLI-команды, переменные окружения, Git-сообщения — английский
- Технические термины (API, REST, JWT, RSSI, WKNN, BSSID и т. д.) сохраняются в Latin-форме без перевода

### Git-сообщения

- Conventional Commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- Текст сообщения — на русском после префикса
- Пример: `feat: добавить endpoint POST /api/fingerprints для приёма радиоотпечатков`

---

## Backend (Python + FastAPI)

### Соглашения именования

- Файлы: `snake_case.py`
- Модули и пакеты: `snake_case`
- Переменные и функции: `snake_case`
- Классы: `PascalCase`
- Константы модуля: `UPPER_SNAKE_CASE`
- Pydantic-схемы: `PascalCaseSchema` или с суффиксом по назначению — `FingerprintCreate`, `FingerprintRead`, `FingerprintInDB`
- SQLAlchemy ORM-модели: `PascalCase` (`User`, `Fingerprint`, `AttendanceLog`)

### Структура backend-модуля

```
backend/
├── app/
│   ├── api/              # FastAPI routers, по одному файлу на ресурс
│   │   └── v1/
│   │       ├── fingerprints.py
│   │       ├── attendance.py
│   │       └── auth.py
│   ├── core/             # Настройки, безопасность, общие зависимости
│   │   ├── config.py     # pydantic-settings
│   │   ├── security.py   # JWT, hash паролей
│   │   └── logging.py    # structlog настройка
│   ├── db/               # Подключение, сессии, миграции
│   │   ├── session.py
│   │   └── base.py
│   ├── models/           # SQLAlchemy ORM-модели
│   ├── schemas/          # Pydantic-схемы для API
│   ├── repositories/     # Слой доступа к данным
│   ├── services/         # Бизнес-логика
│   ├── ml/               # WKNN, Random Forest, обучение и инференс
│   │   ├── wknn.py
│   │   ├── random_forest.py
│   │   ├── features.py   # Извлечение признаков из радиоотпечатков
│   │   └── metrics.py    # RMSE, Detection Probability (ISO/IEC 18305)
│   └── main.py           # точка входа FastAPI
├── alembic/              # миграции БД
├── tests/
│   ├── unit/
│   ├── integration/
│   └── ml/               # тесты ML-моделей с зафиксированными данными
└── pyproject.toml
```

### Обработка ошибок

- Бизнес-исключения — собственные классы, наследники `app.exceptions.AppError`
- Глобальный exception handler в `app/main.py` преобразует `AppError` в RFC 7807 Problem Details
- Никаких голых `except Exception:` — ловим конкретные исключения с явным action
- Возврат HTTP-кодов: 400 для валидации, 401 для auth, 403 для авторизации, 404 для not-found, 409 для конфликтов, 500 — только для непредвиденных ошибок

### Логирование

- `structlog` с JSON-выводом
- Каждый HTTP-запрос получает `correlation_id` (UUID), пробрасывается в логи и в `detail` ответов
- Уровень логирования: `LOG_LEVEL` env-переменная (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- Никаких `print()` в production-коде

### Тестирование

- `pytest` + `pytest-asyncio` + `httpx.AsyncClient`
- Структура: `tests/unit/`, `tests/integration/`, `tests/ml/`
- ML-тесты используют зафиксированные seed и эталонные радиоотпечатки для воспроизводимости
- Метрологические проверки (RMSE, Detection Probability) — отдельный набор тестов с явным эталонным значением

---

## Mobile (Flutter + Dart, Android-only)

### Соглашения именования

- Файлы: `snake_case.dart`
- Классы: `PascalCase`
- Переменные и методы: `camelCase`
- Константы: `lowerCamelCase` с префиксом `k` для глобальных констант (`kApiBaseUrl`)
- Приватные имена: с префиксом `_`

### Структура mobile-модуля

```
mobile/
├── lib/
│   ├── main.dart
│   ├── app/                      # корневая конфигурация приложения
│   ├── core/                     # общие утилиты, константы, ошибки
│   ├── data/
│   │   ├── api/                  # HTTP-клиент (Dio) и DTO
│   │   ├── local/                # sqflite кэш отпечатков
│   │   └── wifi/                 # обёртка wifi_scan/wifi_iot
│   ├── domain/
│   │   ├── models/               # доменные модели
│   │   └── repositories/         # абстракции
│   ├── features/                 # фичи по экранам
│   │   ├── auth/
│   │   ├── scanning/             # фоновое сканирование Wi-Fi
│   │   └── calibration/          # режим администратора (создание радиокарты)
│   └── shared/                   # общие виджеты
├── android/                      # нативная Android-конфигурация
├── test/
└── pubspec.yaml
```

### Архитектура

- Clean Architecture: `presentation` → `domain` → `data`
- State management — выбирается на этапе планирования (Riverpod или Bloc), фиксируется в `ARCHITECTURE.md`
- Все Wi-Fi операции — через единый сервис `WifiScanService` с интерфейсом, чтобы можно было замокать в тестах
- Фоновое сканирование — через `WorkManager` (учитывая ограничения Android 9+ на частоту сканирования: не более 4 сканов за 2 минуты)

### Обработка ошибок

- Result-pattern (`Either<Failure, Success>` через пакет `dartz`) для явной обработки ошибок без исключений в бизнес-логике
- Сетевые ошибки преобразуются в `Failure` с понятным сообщением для пользователя

### Логирование

- Пакет `logger` или `talker` — структурированные логи
- В release-сборке отключаются debug-логи

### Тестирование

- Unit-тесты сервисов и репозиториев
- Widget-тесты ключевых экранов (calibration, scanning)
- Integration-тесты — `integration_test`, проверяют сценарий end-to-end на эмуляторе

---

## Web (React + Vite + TypeScript)

### Соглашения именования

- Файлы компонентов: `PascalCase.tsx` (`AttendanceTable.tsx`)
- Файлы хуков: `useCamelCase.ts` (`useAttendanceQuery.ts`)
- Файлы утилит: `camelCase.ts` (`formatDate.ts`)
- TypeScript-типы и интерфейсы: `PascalCase`, без префикса `I`
- Переменные, функции, props: `camelCase`
- Константы: `UPPER_SNAKE_CASE`

### Структура web-модуля

```
web/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/                  # API-клиент, типы из OpenAPI
│   ├── components/           # переиспользуемые компоненты
│   ├── features/             # фичи по разделам admin-панели
│   │   ├── auth/
│   │   ├── radiomap/         # калибровочная радиокарта
│   │   ├── attendance/       # отчёты по посещаемости
│   │   └── employees/
│   ├── hooks/                # общие хуки
│   ├── lib/                  # утилиты, helpers
│   ├── routes/               # React Router конфигурация
│   └── types/                # глобальные типы
├── tests/
├── package.json
└── vite.config.ts
```

### Архитектура

- Feature-based folders, не layer-based
- Server state — TanStack Query (`@tanstack/react-query`)
- UI state — Zustand (минимально, только когда server state не подходит)
- Нет Redux

### Стилизация

- CSS Modules или Tailwind CSS — выбирается на этапе планирования
- Никаких inline-стилей кроме редких динамических случаев

### Тестирование

- Vitest + React Testing Library для unit и component тестов
- Playwright (через MCP-сервер) для e2e-тестов критичных сценариев

---

## Запреты для всех модулей

- Никаких `TODO`/`FIXME` без привязки к issue или плану в `.ai-factory/plans/`
- Никаких хардкодов API-адресов и секретов — только через env-переменные
- Никакого закомментированного кода, оставленного «на будущее»
- Никаких `console.log` (web/mobile) или `print` (backend) в production-коде
- Никаких magic-чисел в ML-коде — все гиперпараметры WKNN/Random Forest вынесены в `app/ml/config.py` (backend) и зафиксированы в репозитории для воспроизводимости экспериментов
