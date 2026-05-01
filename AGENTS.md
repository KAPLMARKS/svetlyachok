# AGENTS.md

> Структурная карта проекта для AI-агентов и новых разработчиков. Поддерживайте файл в актуальном состоянии при значимых изменениях структуры. Раздел «Документация» поддерживается командой `/aif-docs`.

## Обзор проекта

АИС «Светлячок» — клиент-серверная система для автоматизированного учёта посещаемости сотрудников на базе Wi-Fi-позиционирования внутри закрытых помещений. Метод — RSSI Fingerprinting + WKNN/Random Forest. Полное описание: `.ai-factory/DESCRIPTION.md`.

## Технологический стек

| Слой | Технология |
|------|------------|
| **Mobile (Android-only)** | Flutter + Dart |
| **Backend** | Python 3.12+ + FastAPI |
| **База данных** | PostgreSQL 16+ |
| **ORM** | SQLAlchemy 2.x + Alembic |
| **ML** | scikit-learn (WKNN, Random Forest) |
| **Web admin panel** | React 18 + Vite + TypeScript |
| **Аутентификация** | JWT |
| **Контейнеризация** | Docker + Docker Compose |

## Структура проекта

> Структура отсутствует на момент настройки `/aif`. Базовый каркас будет создан на этапе `/aif-implement`. Рекомендуемая структура (зафиксирована в `.ai-factory/rules/base.md` и будет уточнена в `.ai-factory/ARCHITECTURE.md`):

```
project/
├── .ai-factory/              # Контекст AI-агентов: описание, правила, планы
│   ├── DESCRIPTION.md        # Спецификация проекта
│   ├── ARCHITECTURE.md       # Архитектурные решения (создаётся /aif-architecture)
│   ├── ROADMAP.md            # План вех проекта (создаётся /aif-roadmap)
│   ├── rules/                # Правила и соглашения по коду
│   │   └── base.md           # Базовые правила всех модулей
│   └── plans/                # Планы реализации фич (создаются /aif-plan)
├── .claude/                  # Скиллы и агенты Claude Code
│   ├── skills/               # Установленные скиллы (см. ниже)
│   └── agents/               # Под-агенты (sidecar, coordinators)
├── backend/                  # Python + FastAPI сервер (будет создан)
├── mobile/                   # Flutter Android-приложение (будет создано)
├── web/                      # React + Vite веб-панель администратора (будет создана)
├── .mcp.json                 # Конфигурация MCP-серверов
├── AGENTS.md                 # Этот файл — карта проекта для агентов
└── README.md                 # Точка входа в документацию (создаётся /aif-docs)
```

## Ключевые точки входа

| Файл | Назначение |
|------|------------|
| `.ai-factory/DESCRIPTION.md` | Спецификация проекта, бизнес-требования, нефункциональные требования |
| `.ai-factory/rules/base.md` | Базовые правила и соглашения по коду для всех трёх модулей |
| `.ai-factory/config.yaml` | Конфигурация AI Factory: язык, пути, git-настройки |
| `.mcp.json` | Конфигурация MCP-серверов (postgres, github, playwright) |
| `backend/app/main.py` | Точка входа backend (после `/aif-implement`) |
| `mobile/lib/main.dart` | Точка входа Flutter-приложения (после `/aif-implement`) |
| `web/src/main.tsx` | Точка входа React-приложения (после `/aif-implement`) |

## Документация

| Документ | Путь | Описание |
|----------|------|----------|
| README | `README.md` | Точка входа, краткий обзор и инструкции запуска (будет создан `/aif-docs`) |
| Описание проекта | `.ai-factory/DESCRIPTION.md` | Полная спецификация системы |
| Архитектура | `.ai-factory/ARCHITECTURE.md` | Архитектурные решения, слои, зависимости |
| Базовые правила | `.ai-factory/rules/base.md` | Стиль кода, именование, структура модулей |

## Файлы контекста для AI-агентов

| Файл | Назначение |
|------|------------|
| `AGENTS.md` | Структурная карта проекта (этот файл). Универсальная для всех AI-инструментов |
| `.ai-factory/DESCRIPTION.md` | Полная спецификация: что строим и зачем |
| `.ai-factory/ARCHITECTURE.md` | Архитектурные решения и каркас |
| `.ai-factory/rules/base.md` | Соглашения по стилю и структуре кода |
| `.claude/skills/` | Каталог установленных скиллов (доменные знания) |

## Установленные скиллы (доменные знания)

### Встроенные `aif-*` (AI Factory)

`/aif`, `/aif-architecture`, `/aif-best-practices`, `/aif-build-automation`, `/aif-ci`, `/aif-commit`, `/aif-dockerize`, `/aif-docs`, `/aif-evolve`, `/aif-explore`, `/aif-fix`, `/aif-grounded`, `/aif-implement`, `/aif-improve`, `/aif-loop`, `/aif-plan`, `/aif-qa`, `/aif-reference`, `/aif-review`, `/aif-roadmap`, `/aif-rules`, `/aif-security-checklist`, `/aif-skill-generator`, `/aif-verify`

### Внешние скиллы из skills.sh

| Скилл | Зона ответственности |
|-------|---------------------|
| `fastapi` | Best practices FastAPI и Pydantic-схем |
| `sqlalchemy-alembic-expert-best-practices-code-review` | Соглашения SQLAlchemy ORM и миграций Alembic |
| `supabase-postgres-best-practices` | Производительность и схемы PostgreSQL |
| `flutter-apply-architecture-best-practices` | Слоистая архитектура Flutter (UI / Logic / Data) |
| `flutter-add-integration-test` | Integration-тесты Flutter через `integration_test` |
| `flutter-implement-json-serialization` | Сериализация моделей в Dart (`fromJson`/`toJson`) |
| `vercel-react-best-practices` | Производительность React от Vercel Engineering |

### Рекомендуемые к генерации (custom)

- **`wifi-rssi-wknn`** — domain-specific экспертиза по Wi-Fi RSSI Fingerprinting и алгоритмам WKNN/Random Forest для indoor-позиционирования. Запуск: `/aif-skill-generator wifi-rssi-wknn`
- **`indoor-positioning-metrology`** — метрология ISO/IEC 18305:2016 (RMSE, Detection Probability). Запуск: `/aif-skill-generator indoor-positioning-metrology`

## MCP-серверы

| Сервер | Назначение | Требования |
|--------|------------|------------|
| `postgres` | Прямые SQL-запросы к БД из агента | env `DATABASE_URL` |
| `github` | Управление PR и issues | env `GITHUB_TOKEN` |
| `playwright` | E2E-тесты веб-панели администратора | — |

## Правила для агентов

- **Декомпозиция shell-команд:** не объединять команды git в один компаунд. Это вызывает запросы permission и теряет видимость для пользователя.
  - Неверно: `git checkout main && git pull`
  - Верно: сначала `git checkout main`, затем `git pull origin main`
- **Wi-Fi RSSI методология:** не предлагать альтернативы, дропающие RSSI или Wi-Fi (BLE, magnetic, QR) и не предлагать новое железо. Тема диссертации фиксирована.
- **iOS поддержка:** не добавлять, не предлагать, не «имплементировать на потом». Это методологическое ограничение, отражённое в диссертации (см. `.ai-factory/DESCRIPTION.md`, раздел «Ограничения»).
- **Язык:** артефакты и документация — на русском, идентификаторы и git-сообщения — на английском (см. `.ai-factory/rules/base.md`).
- **ML-воспроизводимость:** все гиперпараметры WKNN/Random Forest и random seeds фиксируются в `backend/app/ml/config.py` и не хардкодятся в коде модели.
