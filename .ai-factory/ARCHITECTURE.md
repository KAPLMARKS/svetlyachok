# Архитектура: Clean Architecture (адаптация для Python + FastAPI)

## Обзор

Backend-сервис АИС «Светлячок» построен по принципам Clean Architecture (Robert C. Martin). Зависимости направлены строго внутрь: внешние слои (FastAPI, SQLAlchemy, scikit-learn) знают о внутренних, но не наоборот. Доменный слой не зависит ни от чего, кроме стандартной библиотеки и Pydantic.

Выбор обоснован спецификой магистерской диссертации:

- **Тестируемость алгоритмов WKNN/Random Forest:** ML-логика отделена от инфраструктурного кода. Это позволяет проводить независимые метрологические испытания (RMSE, Detection Probability по ISO/IEC 18305:2016) без поднятия HTTP-сервера или БД.
- **Воспроизводимость экспериментов:** доменные модели и use cases ML-инференса не привязаны к фреймворку. Любой тест с зафиксированным набором данных и seed детерминирован.
- **Поддержка ERP-интеграции (1С):** изоляция domain от infrastructure упрощает добавление adapters для разных учётных систем без касания бизнес-логики.
- **Академическая ясность:** диссертационный код должен быть читаем и обоснован. Clean Architecture даёт чёткие слои, которые легко описать в разделе «Программная реализация».

Mobile (Flutter) и Web (React) — отдельные приложения; они потребляют backend через REST API и имеют собственные архитектуры (раздел «Клиентские приложения»).

## Обоснование решения

| Критерий | Значение | Влияние на выбор |
|----------|----------|------------------|
| **Размер команды** | 1 (solo, дипломник) | За Layered, против Microservices/DDD |
| **Сложность домена** | Средне-высокая (ML + классификация + time tracking + интеграция) | За Clean Architecture (изоляция бизнес-правил) |
| **Требования к тестируемости** | Высокие (метрология ISO/IEC 18305) | За Clean Architecture (domain без инфраструктурных зависимостей) |
| **Требования к производительности** | Низкие (пилот на ~50 сотрудников вуза) | Не доминирует |
| **Долгосрочность** | Низкая (учебный проект) | Не за DDD/Microservices |
| **Тех.стек** | Python 3.12+, FastAPI, SQLAlchemy 2, scikit-learn | Совместим с Clean Architecture через Protocols |

**Ключевой фактор:** изоляция ML-логики и доменных правил для воспроизводимых научных экспериментов.

## Структура папок (backend/)

```
backend/
├── app/
│   ├── domain/                           # Слой Domain (внутренний, без зависимостей)
│   │   ├── radiomap/
│   │   │   ├── entities.py               # Fingerprint, Calibration, RadioPoint
│   │   │   ├── value_objects.py          # RSSIVector, BSSID, AccessPoint
│   │   │   ├── repositories.py           # Protocol: FingerprintRepository
│   │   │   └── services.py               # Доменные сервисы (валидация отпечатка)
│   │   ├── positioning/
│   │   │   ├── entities.py               # PositionEstimate, Zone, ZoneClassification
│   │   │   ├── value_objects.py          # Coordinates, Confidence
│   │   │   ├── classifiers.py            # Protocol: PositionClassifier (контракт WKNN/RF)
│   │   │   └── services.py
│   │   ├── attendance/
│   │   │   ├── entities.py               # AttendanceLog, WorkSession, Lateness
│   │   │   ├── value_objects.py          # WorkInterval, ScheduleRule
│   │   │   ├── repositories.py           # Protocol: AttendanceRepository
│   │   │   └── services.py               # Расчёт часов, опозданий, переработок
│   │   ├── employees/
│   │   │   ├── entities.py               # Employee, Role
│   │   │   ├── value_objects.py          # EmployeeId, CorporateCredentials
│   │   │   └── repositories.py
│   │   └── shared/
│   │       ├── exceptions.py             # AppError и наследники доменных ошибок
│   │       └── types.py                  # Базовые типы
│   │
│   ├── application/                      # Слой Application (use cases)
│   │   ├── radiomap/
│   │   │   ├── submit_fingerprint.py     # Use case: приём радиоотпечатка с устройства
│   │   │   └── calibrate_radiomap.py     # Use case: создание/обновление эталонной точки
│   │   ├── positioning/
│   │   │   ├── classify_location.py      # Use case: классификация местоположения
│   │   │   └── train_classifier.py       # Use case: обучение модели на калиброванных данных
│   │   ├── attendance/
│   │   │   ├── record_attendance.py      # Use case: запись присутствия
│   │   │   ├── compute_work_hours.py     # Use case: расчёт отработанных часов
│   │   │   └── export_for_erp.py         # Use case: выгрузка в формате 1С
│   │   ├── employees/
│   │   │   ├── authenticate.py
│   │   │   └── manage_employee.py
│   │   └── ports/                        # Контракты внешних сервисов
│   │       ├── notification.py           # Протокол отправки уведомлений
│   │       └── erp_client.py             # Протокол интеграции с 1С
│   │
│   ├── infrastructure/                   # Слой Infrastructure (внешний, реализует Protocols)
│   │   ├── db/
│   │   │   ├── session.py                # SQLAlchemy AsyncSession factory
│   │   │   ├── base.py                   # DeclarativeBase
│   │   │   └── orm/                      # SQLAlchemy ORM-модели
│   │   │       ├── radiomap.py
│   │   │       ├── attendance.py
│   │   │       └── employees.py
│   │   ├── repositories/                 # Реализации domain.*.repositories.py
│   │   │   ├── radiomap_repository.py    # FingerprintRepository (SQLAlchemy)
│   │   │   ├── attendance_repository.py
│   │   │   └── employees_repository.py
│   │   ├── ml/                           # Реализации domain.positioning.classifiers.py
│   │   │   ├── wknn_classifier.py        # PositionClassifier через scikit-learn KNN
│   │   │   ├── random_forest_classifier.py
│   │   │   ├── features.py               # Извлечение признаков из радиоотпечатков
│   │   │   ├── metrics.py                # RMSE, Detection Probability (ISO/IEC 18305)
│   │   │   └── config.py                 # Гиперпараметры (k, weights, n_estimators)
│   │   ├── erp/
│   │   │   └── one_c_client.py           # Реализация ports.erp_client (REST 1С)
│   │   ├── auth/
│   │   │   ├── jwt_provider.py           # Кодирование/декодирование JWT
│   │   │   └── password_hasher.py        # bcrypt
│   │   └── logging/
│   │       └── structlog_config.py
│   │
│   ├── presentation/                     # Слой Presentation (FastAPI)
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── fingerprints.py       # POST /api/v1/fingerprints
│   │   │       ├── calibration.py        # POST /api/v1/calibration/points
│   │   │       ├── positioning.py        # POST /api/v1/positioning/classify
│   │   │       ├── attendance.py         # GET /api/v1/attendance/...
│   │   │       ├── employees.py
│   │   │       └── auth.py               # POST /api/v1/auth/login
│   │   ├── schemas/                      # Pydantic-схемы запросов/ответов
│   │   │   ├── radiomap.py               # FingerprintCreate, FingerprintRead
│   │   │   ├── positioning.py
│   │   │   ├── attendance.py
│   │   │   └── employees.py
│   │   ├── dependencies.py               # FastAPI Depends() для DI
│   │   └── exception_handlers.py         # Маппинг AppError → RFC 7807
│   │
│   ├── core/                             # Композиция и cross-cutting
│   │   ├── config.py                     # Settings через pydantic-settings
│   │   ├── container.py                  # DI-контейнер: связывает Protocols с реализациями
│   │   └── security.py                   # Обёртки безопасности
│   │
│   └── main.py                           # Точка входа: создание FastAPI app
│
├── alembic/                              # Миграции БД
│   └── versions/
├── tests/
│   ├── unit/                             # Тесты domain и application слоёв (без БД, без HTTP)
│   │   ├── domain/
│   │   └── application/
│   ├── integration/                      # Тесты infrastructure слоя
│   │   ├── repositories/
│   │   └── api/
│   └── ml/                               # Метрологические тесты ML-моделей
│       ├── test_wknn_rmse.py
│       ├── test_random_forest_rmse.py
│       └── fixtures/                     # Зафиксированные радиоотпечатки + seeds
└── pyproject.toml
```

## Правила зависимостей

```
┌──────────────────────────────────────────────────────────┐
│                       Presentation                        │
│                       (FastAPI)                           │
│                          ↓                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │                   Application                       │  │
│  │               (use cases, ports)                    │  │
│  │                       ↓                             │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │                    Domain                     │  │  │
│  │  │   (entities, value objects, repositories,     │  │  │
│  │  │    classifiers как Protocol)                  │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │                  Infrastructure                     │  │
│  │     (SQLAlchemy, scikit-learn, JWT, 1С client)     │  │
│  │   реализует Protocols из Domain и Application       │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Разрешённые направления зависимостей

- ✅ `presentation` → `application`, `core`
- ✅ `application` → `domain`
- ✅ `infrastructure` → `domain`, `application` (реализует их Protocols)
- ✅ `core` → всё остальное (composition root)

### Запрещённые направления

- ❌ `domain` → `application`, `infrastructure`, `presentation` (домен ничего не знает о внешнем мире)
- ❌ `application` → `infrastructure` (use cases работают только через Protocols)
- ❌ `application` → `presentation`
- ❌ `infrastructure` → `presentation`
- ❌ `presentation` → `infrastructure` напрямую (только через Depends() с Protocol-типами)

## Связь между слоями и модулями

### DI через Protocol + FastAPI Depends

Все use cases получают зависимости через конструктор. Связывание с реализациями — в `app/core/container.py` и `app/presentation/dependencies.py`. FastAPI `Depends()` инжектит реализации.

### Связь между поддоменами

- Use case одного поддомена может вызвать use case другого поддомена через `application/`-уровень (никогда напрямую через repositories).
- Например: `attendance.record_attendance` после получения `PositionEstimate` от `positioning.classify_location` создаёт `AttendanceLog`.
- Поддомены НЕ импортируют друг у друга domain-слой кроме общего `domain/shared/`.

### События (опционально, для расширения)

Если потребуется реакция на доменные события (например, «сотрудник пересёк зону опоздания» → уведомление руководителю), используется domain event pattern: события публикуются из use cases в шину `application/ports/event_bus.py` и обрабатываются подписчиками.

## Ключевые принципы

1. **Domain — pure code.** Никаких импортов FastAPI, SQLAlchemy, scikit-learn в `app/domain/`. Только стандартная библиотека Python и Pydantic для value objects при необходимости валидации.
2. **Repositories как Protocol.** Доменный слой объявляет интерфейс через `typing.Protocol`. Реализация — в `infrastructure/repositories/`. Это позволяет тестировать use cases с in-memory fake-репозиториями.
3. **ML-классификаторы как Protocol.** `PositionClassifier` (Protocol) живёт в `domain/positioning/classifiers.py`. Реализации `WknnClassifier` и `RandomForestClassifier` — в `infrastructure/ml/`. Это критично для метрологических тестов: можно сравнить любые классификаторы на одном test set.
4. **Гиперпараметры ML — в config.** `infrastructure/ml/config.py` хранит k, weights, n_estimators, random_state. Никаких magic-чисел в коде моделей. Все параметры обучения версионируются в репозитории для воспроизводимости.
5. **Use case = команда или запрос.** Каждый use case — один сценарий, один публичный метод (`execute()` или `__call__`). Не делать «service классы» с десятком методов.
6. **Pydantic-схемы только в presentation.** API-контракты в `presentation/schemas/`. Внутри домена — собственные `@dataclass` или Pydantic models с другим назначением. Не возвращать ORM-модели из use cases.
7. **Транзакционные границы — в use case.** Use case открывает Unit of Work (если нужны множественные изменения), не отдельные репозитории.

## Примеры кода

### Пример 1: Доменный Protocol и реализация

`domain/radiomap/repositories.py`:
```python
from typing import Protocol
from .entities import Fingerprint
from .value_objects import BSSID

class FingerprintRepository(Protocol):
    """Контракт хранилища радиоотпечатков. Не зависит от SQLAlchemy."""

    async def add(self, fingerprint: Fingerprint) -> None: ...
    async def get_by_employee(self, employee_id: str) -> list[Fingerprint]: ...
    async def find_calibrated_near(self, bssids: list[BSSID]) -> list[Fingerprint]: ...
```

`infrastructure/repositories/radiomap_repository.py`:
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.repositories import FingerprintRepository
from app.infrastructure.db.orm.radiomap import FingerprintORM

class SqlAlchemyFingerprintRepository(FingerprintRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, fingerprint: Fingerprint) -> None:
        orm = FingerprintORM.from_domain(fingerprint)
        self._session.add(orm)
        await self._session.flush()

    async def get_by_employee(self, employee_id: str) -> list[Fingerprint]:
        stmt = select(FingerprintORM).where(FingerprintORM.employee_id == employee_id)
        result = await self._session.execute(stmt)
        return [row.to_domain() for row in result.scalars()]

    async def find_calibrated_near(self, bssids):
        # ... реализация поиска
        ...
```

### Пример 2: Use case без знания инфраструктуры

`application/positioning/classify_location.py`:
```python
from dataclasses import dataclass
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.positioning.classifiers import PositionClassifier
from app.domain.positioning.entities import ZoneClassification
from app.domain.radiomap.repositories import FingerprintRepository

@dataclass
class ClassifyLocationCommand:
    employee_id: str
    rssi_vector: RSSIVector

class ClassifyLocationUseCase:
    def __init__(
        self,
        classifier: PositionClassifier,
        fingerprint_repo: FingerprintRepository,
    ) -> None:
        self._classifier = classifier
        self._fingerprint_repo = fingerprint_repo

    async def execute(self, cmd: ClassifyLocationCommand) -> ZoneClassification:
        # Доменная логика — никакой SQLAlchemy, никакого FastAPI здесь
        calibrated = await self._fingerprint_repo.find_calibrated_near(
            cmd.rssi_vector.bssids()
        )
        return self._classifier.classify(cmd.rssi_vector, calibrated)
```

### Пример 3: WKNN-классификатор реализует доменный Protocol

`domain/positioning/classifiers.py`:
```python
from typing import Protocol
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.positioning.entities import ZoneClassification

class PositionClassifier(Protocol):
    """Контракт классификатора позиции. Реализации: WKNN, Random Forest."""

    def classify(
        self,
        observation: RSSIVector,
        calibration_set: list[Fingerprint],
    ) -> ZoneClassification: ...
```

`infrastructure/ml/wknn_classifier.py`:
```python
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from app.domain.positioning.classifiers import PositionClassifier
from app.domain.positioning.entities import ZoneClassification
from app.infrastructure.ml.config import WknnConfig
from app.infrastructure.ml.features import build_feature_matrix

class WknnClassifier(PositionClassifier):
    def __init__(self, config: WknnConfig) -> None:
        self._config = config

    def classify(self, observation, calibration_set):
        X, y = build_feature_matrix(calibration_set)
        clf = KNeighborsClassifier(
            n_neighbors=self._config.k,
            weights="distance",  # WKNN — взвешенный по расстоянию
            metric=self._config.metric,
        )
        clf.fit(X, y)
        observation_vector = build_feature_matrix([observation])[0]
        zone = clf.predict([observation_vector[0]])[0]
        confidence = clf.predict_proba([observation_vector[0]]).max()
        return ZoneClassification(zone=zone, confidence=confidence)
```

### Пример 4: FastAPI router как тонкий слой

`presentation/api/v1/positioning.py`:
```python
from fastapi import APIRouter, Depends, status
from app.application.positioning.classify_location import (
    ClassifyLocationCommand,
    ClassifyLocationUseCase,
)
from app.presentation.dependencies import get_classify_location_use_case
from app.presentation.schemas.positioning import (
    ClassifyRequest,
    ClassifyResponse,
)

router = APIRouter(prefix="/positioning", tags=["positioning"])

@router.post(
    "/classify",
    response_model=ClassifyResponse,
    status_code=status.HTTP_200_OK,
)
async def classify_location(
    request: ClassifyRequest,
    use_case: ClassifyLocationUseCase = Depends(get_classify_location_use_case),
):
    """POST /api/v1/positioning/classify — классификация позиции по радиоотпечатку."""
    cmd = ClassifyLocationCommand(
        employee_id=request.employee_id,
        rssi_vector=request.to_rssi_vector(),
    )
    classification = await use_case.execute(cmd)
    return ClassifyResponse.from_domain(classification)
```

### Пример 5: Composition root в `core/container.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.application.positioning.classify_location import ClassifyLocationUseCase
from app.infrastructure.repositories.radiomap_repository import SqlAlchemyFingerprintRepository
from app.infrastructure.ml.wknn_classifier import WknnClassifier
from app.infrastructure.ml.config import WknnConfig

def build_classify_location_use_case(session: AsyncSession) -> ClassifyLocationUseCase:
    """Composition root для use case ClassifyLocation."""
    return ClassifyLocationUseCase(
        classifier=WknnClassifier(WknnConfig()),
        fingerprint_repo=SqlAlchemyFingerprintRepository(session),
    )
```

`presentation/dependencies.py`:
```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.container import build_classify_location_use_case
from app.infrastructure.db.session import get_session

def get_classify_location_use_case(
    session: AsyncSession = Depends(get_session),
):
    return build_classify_location_use_case(session)
```

## Анти-паттерны

- ❌ **Импорт `sqlalchemy` или `fastapi` в `app/domain/`.** Доменный слой обязан быть независим. Если такой импорт появился — выносить логику в infrastructure/application.
- ❌ **Сквозные «Service»-классы с 10+ методами.** Использовать use case на сценарий — один публичный `execute()` или `__call__`.
- ❌ **Использование ORM-моделей в API-роутерах напрямую.** Всегда конвертировать в Pydantic-схему через `.from_domain()` или явный mapper.
- ❌ **Magic-числа в ML-коде.** Все гиперпараметры (k, n_estimators, random_state, weights) — в `infrastructure/ml/config.py` или в передаваемом `WknnConfig`.
- ❌ **Зависимость use case от конкретного класса репозитория.** Use cases получают `FingerprintRepository` (Protocol), не `SqlAlchemyFingerprintRepository`.
- ❌ **HTTP-обработка в use case.** Use cases возвращают доменные объекты или поднимают доменные исключения. Преобразование в HTTP-коды — в `presentation/exception_handlers.py`.
- ❌ **Прямые SQL-запросы из presentation/api.** Только через use case → repository.
- ❌ **Хранение состояния в use case.** Use case — stateless, всё передаётся в `execute()`.
- ❌ **Кросс-доменные импорты domain.** Например, `domain/attendance/` не импортирует `domain/positioning/`. Кросс-доменная композиция — в `application/`.

---

## Клиентские приложения

### Mobile (Flutter, Android-only)

Mobile-приложение использует свою архитектуру согласно скиллу `flutter-apply-architecture-best-practices` (слоистая Flutter-архитектура: UI → Logic → Data).

```
mobile/lib/
├── data/                 # API клиент, Wi-Fi сервис, локальный кэш
├── domain/               # Модели и репозитории (абстракции)
├── features/             # Фичи: auth, scanning, calibration
├── shared/               # Общие виджеты
└── main.dart
```

Подробности — в `.ai-factory/rules/base.md` (раздел Mobile).

### Web admin panel (React + Vite + TypeScript)

Web-админка использует feature-based структуру согласно скиллу `vercel-react-best-practices`.

```
web/src/
├── api/                  # API клиент с типами из OpenAPI-схемы backend
├── features/             # auth, radiomap, attendance, employees
├── components/           # переиспользуемые компоненты
├── hooks/                # общие хуки
└── routes/               # React Router конфиг
```

Подробности — в `.ai-factory/rules/base.md` (раздел Web).

### Контракт между клиентами и backend

- Backend публикует OpenAPI-спецификацию по `/openapi.json`
- Клиенты генерируют типы из этой спецификации (mobile — через build_runner, web — через `openapi-typescript`)
- Версионирование через URL-префикс `/api/v1/`, `/api/v2/` при breaking changes
