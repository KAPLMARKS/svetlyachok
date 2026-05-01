# Roadmap проекта АИС «Светлячок»

> Система учёта посещаемости на базе Wi-Fi RSSI fingerprinting (WKNN / Random Forest). **Главная задача — рабочий продукт, который запускается локально на одном компьютере и проходит E2E-сценарий**: admin создаёт сотрудника → калибрует зоны → mobile отправляет отпечатки → web показывает учёт времени. Без Docker, без production-инфраструктуры — только локальный запуск backend + веб в браузере + APK на телефоне.

## Вехи

- [x] **Настройка контекста AI Factory** — DESCRIPTION.md, ARCHITECTURE.md, AGENTS.md, базовые правила, скиллы и MCP установлены и сконфигурированы
- [x] **Базовый каркас backend** — FastAPI scaffold по Clean Architecture, настройка `pydantic-settings`, structlog-логирование, healthcheck endpoint, базовый exception handler RFC 7807
- [x] **База данных и миграции** — PostgreSQL подключение через SQLAlchemy 2.x async, Alembic-миграции, ORM-модели (employees, zones, fingerprints, attendance_logs), seed-скрипты для тестовых данных
- [x] **Аутентификация (JWT)** — login/refresh endpoints, bcrypt хеши паролей, защита роутов через FastAPI Depends, rate limiting на /auth
- [x] **Управление сотрудниками и зонами** — CRUD employees, ролей, рабочих зон (рабочее место, коридор, переговорная, вне офиса) — backend API
- [x] **Приём радиоотпечатков и калибровка** — endpoint POST `/api/v1/fingerprints` для приёма с устройства, endpoint POST `/api/v1/calibration/points` для эталонных точек admin-режима
- [x] **ML-классификаторы (WKNN + Random Forest)** — реализация `PositionClassifier` Protocol через scikit-learn (KNN с distance-weighting и Random Forest), извлечение признаков из RSSI-векторов, конфигурация гиперпараметров в `infrastructure/ml/config.py`
- [ ] **Учёт рабочего времени** — AttendanceLog автоматически создаётся при `POST /api/v1/positioning/classify`; use case `RecordAttendanceUseCase` открывает/закрывает сессии по смене зоны и таймауту неактивности; расчёт `work_hours`, опозданий и переработок относительно `Employee.schedule_start/end`; REST API `GET /api/v1/attendance` с фильтрами (employee_id, from, to) и агрегацией по периоду. **Без интеграции с 1С/ERP — простой REST API.**
- [ ] **Backend MVP-доработки** — критичные для рабочего продукта задачи, без которых mobile/web не заработают:
  - **ML cache invalidation**: после CRUD калибровочных точек singleton-классификатор должен переобучиться без рестарта backend (иначе после `/calibration/points` admin не увидит изменений на mobile до перезапуска)
  - **Bulk fingerprints**: `POST /api/v1/fingerprints/batch` для отправки накопленного офлайн-кэша с mobile (нужно для sqflite-кэша + WorkManager: телефон не всегда онлайн, копит отпечатки и выгружает пачкой)
  - **Logout endpoint**: `POST /api/v1/auth/logout` (минимальная реализация — клиент стирает токены; blacklist jti — отложен) для кнопки «Выйти» в web-панели
- [ ] **Mobile-приложение (Flutter, Android-only)** — экраны auth и сканирования, фоновое Wi-Fi-сканирование через WorkManager (с учётом throttling Android 9+: не более 4 сканов за 2 минуты), режим администратора для калибровки зон, локальный кэш `sqflite` неотправленных отпечатков с автоматической синхронизацией через bulk-endpoint при появлении сети
- [ ] **Web-панель администратора (React + Vite + TypeScript)** — экраны auth, CRUD employees и zones, визуализация калибровочной радиокарты, отчёты по посещаемости (work_hours, опоздания, текущая зона сотрудника)
- [ ] **Локальный запуск + инструкция** — финальная веха. Документ `docs/local-setup.md` (на русском) описывает шаг за шагом, что нужно установить и как запустить всю систему на одном компьютере + телефон. Никакого Docker, nginx, production-конфигов.
  1. **Что нужно установить на компьютер** (Windows 11 Pro):
     - Python 3.13 (с официального сайта, добавить в PATH)
     - PostgreSQL 16 (installer EnterpriseDB, запомнить пароль `postgres`)
     - Node.js 20 LTS + npm
     - Flutter SDK 3.24+ + Android Studio (для сборки APK)
     - ADB (Android Debug Bridge) — для установки APK через USB
  2. **Подготовка БД**:
     - Через `psql` или pgAdmin создать БД `svetlyachok`
     - Скопировать `backend/.env.example` → `backend/.env`, прописать `DATABASE_URL=postgresql+asyncpg://postgres:<пароль>@localhost:5432/svetlyachok` и `JWT_SECRET=<любая длинная случайная строка>`
     - Из `backend/`: `pip install -e ".[dev]"`, затем `alembic upgrade head` (миграции), затем `python -m app.scripts.seed` (тестовый admin + 4 зоны)
  3. **Запуск backend**: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` — Swagger по адресу `http://localhost:8000/docs`. Узнать локальный IP компьютера (`ipconfig`) — он понадобится телефону.
  4. **Запуск web**: из `web/`: `npm install`, `npm run dev` — открыть `http://localhost:5173`, залогиниться admin'ом, создать сотрудника, накалибровать 4 зоны (минимум 3 точки на зону).
  5. **Сборка APK**: из `mobile/`: `flutter build apk --release` → `mobile/build/app/outputs/flutter-apk/app-release.apk`. В коде указать `BACKEND_URL=http://<локальный-IP-компьютера>:8000` (через `--dart-define` или `.env`). Установить на телефон: `adb install app-release.apk` (USB-debugging) или скопировать APK на телефон и установить из проводника (разрешить «Установка из неизвестных источников»).
  6. **Телефон + компьютер должны быть в одной Wi-Fi-сети**. Файрвол Windows должен пропускать входящие на 8000.
  7. **E2E-сценарий вручную (5 минут)**:
     - Залогиниться в mobile сотрудником, отправить fingerprint
     - `/positioning/classify` возвращает корректную зону
     - AttendanceLog создаётся, web-панель показывает текущую зону и накопленные `work_hours`
  8. **Прохождение сценария = рабочий продукт.** Это финальная веха проекта.

## Завершено

| Веха | Дата |
|------|------|
| Настройка контекста AI Factory | 2026-05-01 |
| Базовый каркас backend | 2026-05-01 |
| База данных и миграции | 2026-05-01 |
| Аутентификация (JWT) | 2026-05-01 |
| Управление сотрудниками и зонами | 2026-05-01 |
| Приём радиоотпечатков и калибровка | 2026-05-01 |
| ML-классификаторы (WKNN + Random Forest) | 2026-05-01 |
| Учёт рабочего времени | 2026-05-02 |

## Что намеренно НЕ в roadmap (отложено или отменено)

Эти задачи могут быть полезны в будущем, но не блокируют рабочий продукт MVP:

**Отменено:**

- **Полевые испытания и сбор реальных данных в вузе** — продукт тестируется на синтетических данных и через локальный E2E-сценарий
- **Метрологическая оценка по ISO/IEC 18305:2016** — метрики уже считаются в `tests/ml/` на синтетике (Detection Probability, confusion matrix); реальная оценка проводилась бы при наличии полевых данных
- **Production-развёртывание (Docker Compose, nginx, release-серверы)** — приоритет — локальный запуск на одном компьютере; production-конфиг не нужен
- **Написание магистерской диссертации** — фокус сдвинут с диссертационного исследования на рабочий продукт
- **1С/ERP интеграция** — учёт времени делается простым REST API без формат-специфичного экспорта

**Отложенные backend-задачи (можно добавить, если станут проблемой):**

- **ML model persistence через joblib** — на текущих данных (~10 калибровочных точек на зону) обучение занимает миллисекунды; persistence имеет смысл только при росте калибровки до тысяч точек
- **Дедупликация fingerprints по окну captured_at** — микро-оптимизация для production; на пилотных объёмах не нужна
- **Rate limit на `/fingerprints`** — anti-DoS защита; не критична для локальной сети с одним пользователем
- **Token rotation + blacklist `jti`** — серьёзная security-задача; для MVP достаточно базовой JWT-проверки и короткого TTL access-токена
- **Force password change at first login** — нужно когда admin раздаёт временные пароли многим пользователям; для тестового сценария admin сам создаёт себе и сотруднику
- **Password strength validation (zxcvbn)** — не критично на пилоте
- **Audit log в БД (`audit_log` таблица)** — observability для production; на пилоте достаточно structlog в stdout
- **Hyperparameter tuning через Optuna** — имеет смысл только на реальных полевых данных
- **Ensemble (WKNN + RF voting)** — на текущих метриках одиночные классификаторы дают DP=1.0 на синтетике
- **Confidence threshold (отказ от классификации при низком confidence)** — добавим, если станет проблемой на реальных данных
- **Per-zone classifiers (одна модель на каждую зону)** — multiclass single-classifier — стандарт для indoor positioning
- **Multi-tenancy (несколько вузов в одной инсталляции)** — не нужен для рабочего продукта
- **Партицирование `fingerprints` и `attendance_logs`** — не нужно: пилотные объёмы; range-partitioning по `captured_at` при > 10M строк
- **Soft-delete для zones (`archived_at`)** — не нужен: hard-delete с FK RESTRICT даёт корректное поведение
- **Cursor-based pagination** — не нужен: limit/offset работает на пилоте
- **Hard-delete employees (GDPR)** — не нужен: soft через `is_active=false` достаточно
- **MFA, password reset через email** — не критично для пилотного запуска
- **Online learning (warm_start RF)** — full retrain дешевле на пилотных объёмах
