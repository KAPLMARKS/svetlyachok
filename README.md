# АИС «Светлячок»

> Indoor-позиционирование и автоматизированный учёт посещаемости на базе Wi-Fi RSSI fingerprinting.

Программный комплекс для автоматизации учёта рабочего времени сотрудников через определение их местоположения в помещениях по уровню сигнала Wi-Fi от существующих корпоративных точек доступа. Использует алгоритмы машинного обучения (WKNN, Random Forest) для классификации зон без необходимости закупки специализированного оборудования. Разрабатывается в рамках магистерской диссертации.

## Быстрый старт

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate           # Linux/macOS
.venv\Scripts\activate               # Windows
pip install -e ".[dev]"
cp .env.example .env                 # отредактируйте DATABASE_URL и JWT_SECRET
uvicorn app.main:app --reload --port 8000
```

Проверка: откройте http://localhost:8000/api/v1/health — должен вернуть `{"status":"ok"}`.

## Ключевые возможности

- **Wi-Fi RSSI Fingerprinting** — позиционирование по уровню сигнала от стандартных точек доступа без дополнительного оборудования
- **WKNN + Random Forest** — два классификатора для сравнительного анализа точности по ISO/IEC 18305:2016
- **Clean Architecture** — изолированный доменный слой для тестируемости и воспроизводимости ML-экспериментов
- **REST API** — интеграция с ERP/HRM-системами (1C и аналоги) через OpenAPI-спецификацию
- **Мобильное приложение** — Flutter (Android), фоновое сканирование Wi-Fi и калибровка радиокарты
- **Веб-панель администратора** — React + TypeScript для управления зонами, отчётов и визуализации радиокарты

## Архитектура

Проект состоит из трёх независимых модулей:

| Модуль | Стек | Назначение |
|--------|------|-----------|
| `backend/` | Python 3.12 + FastAPI + PostgreSQL + scikit-learn | REST API, ML-классификация, учёт времени |
| `mobile/` | Flutter (Android) | Сканирование Wi-Fi, режим калибровки |
| `web/` | React + Vite + TypeScript | Админ-панель, отчёты, радиокарта |

Подробное описание архитектурных решений: [.ai-factory/ARCHITECTURE.md](.ai-factory/ARCHITECTURE.md)

## Документация

| Раздел | Описание |
|--------|----------|
| [Начало работы](docs/getting-started.md) | Установка, конфигурация, первый запуск |
| [Архитектура](docs/architecture.md) | Clean Architecture, слои, зависимости |
| [API Reference](docs/api.md) | REST endpoints, контракты, форматы ошибок |
| [Конфигурация](docs/configuration.md) | Переменные окружения, настройки |
| [Учёт рабочего времени](docs/attendance.md) | AttendanceLog, логика сессий, REST API `/attendance` |

## Контекст для AI-агентов

Проект использует [AI Factory](https://github.com/lee-to/ai-factory) workflow:

- [`AGENTS.md`](AGENTS.md) — карта проекта для AI-агентов
- [`.ai-factory/DESCRIPTION.md`](.ai-factory/DESCRIPTION.md) — полная спецификация
- [`.ai-factory/ARCHITECTURE.md`](.ai-factory/ARCHITECTURE.md) — архитектурные решения
- [`.ai-factory/ROADMAP.md`](.ai-factory/ROADMAP.md) — вехи проекта
- [`.claude/skills/wifi-rssi-wknn/`](.claude/skills/wifi-rssi-wknn/) — domain-скилл по RSSI/WKNN

## Лицензия

MIT
