# Roadmap проекта АИС «Светлячок»

> Магистерская диссертация: исследование методов Wi-Fi-позиционирования (RSSI Fingerprinting + WKNN/Random Forest) для систем учёта посещаемости в закрытых помещениях.

## Вехи

- [x] **Настройка контекста AI Factory** — DESCRIPTION.md, ARCHITECTURE.md, AGENTS.md, базовые правила, скиллы и MCP установлены и сконфигурированы
- [x] **Базовый каркас backend** — FastAPI scaffold по Clean Architecture, настройка `pydantic-settings`, structlog-логирование, healthcheck endpoint, базовый exception handler RFC 7807
- [x] **База данных и миграции** — PostgreSQL подключение через SQLAlchemy 2.x async, Alembic-миграции, ORM-модели (employees, zones, fingerprints, attendance_logs), seed-скрипты для тестовых данных
- [x] **Аутентификация (JWT)** — login/refresh endpoints, bcrypt хеши паролей, защита роутов через FastAPI Depends, rate limiting на /auth
- [x] **Управление сотрудниками и зонами** — CRUD employees, ролей, рабочих зон (рабочее место, коридор, переговорная, вне офиса) — backend API
- [x] **Приём радиоотпечатков и калибровка** — endpoint POST `/api/v1/fingerprints` для приёма с устройства, endpoint POST `/api/v1/calibration/points` для эталонных точек admin-режима
- [x] **ML-классификаторы (WKNN + Random Forest)** — реализация `PositionClassifier` Protocol через scikit-learn (KNN с distance-weighting и Random Forest), извлечение признаков из RSSI-векторов, конфигурация гиперпараметров в `infrastructure/ml/config.py`
- [ ] **Учёт рабочего времени и интеграция с 1С/ERP** — расчёт work_hours, опозданий, переработок; экспорт по REST API в формате, совместимом с 1С; OpenAPI-документация эндпоинтов
- [ ] **Mobile-приложение (Flutter, Android-only)** — экраны auth и сканирования, фоновое Wi-Fi-сканирование через WorkManager (с учётом throttling Android 9+), режим администратора для калибровки, локальный кэш sqflite неотправленных отпечатков
- [ ] **Web-панель администратора (React + Vite + TypeScript)** — экраны auth, визуализация радиокарты, управление зонами и сотрудниками, отчёты по посещаемости, графики опозданий
- [ ] **Полевые испытания и сбор данных в вузе** — реальные измерения в выделенных помещениях, заполнение калибровочной радиокарты, сбор тест-сета для оценки точности
- [ ] **Метрологическая оценка по ISO/IEC 18305:2016** — расчёт RMSE и Detection Probability на тест-сете, сравнение WKNN vs Random Forest на одних данных, оптимизация гиперпараметров, протоколы испытаний
- [ ] **Развёртывание (Docker, Android APK)** — production-конфигурация Docker Compose (backend + PostgreSQL + nginx), сборка release Android APK, веб-панель в production
- [ ] **Написание дипломной работы (Markdown → DOCX через pandoc)** — полная магистерская диссертация: введение, обзор методов indoor-позиционирования, обоснование выбора RSSI Fingerprinting, описание программной реализации, метрологические результаты, заключение, список литературы, приложения. Финальная конвертация Markdown → DOCX командой `pandoc` (опционально: ГОСТ-форматирование через template.docx или Python-скрипт `python-docx`)

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
