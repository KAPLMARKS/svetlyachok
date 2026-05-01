# Учёт рабочего времени

Документ описывает реализацию вехи «Учёт рабочего времени» MVP АИС
«Светлячок»: как `AttendanceLog` авто-создаётся при классификации
позиции, как считаются `work_hours`, опоздания и переработки, как
устроен REST API `/api/v1/attendance`.

**Без интеграции с 1С/ERP** — простой REST API для web-панели и
отчётов. Интеграция вынесена в раздел «не в roadmap».

## Связь с другими вехами

- **Зависит от:** «ML-классификаторы (WKNN + Random Forest)» — `/classify`
  возвращает `zone_id` + `zone_type`, на основе которых открывается/
  закрывается сессия.
- **Использует:** `Employee.schedule_start/end` (веха «Управление
  сотрудниками и зонами») — для расчёта `late` и `overtime`.
- **Будет использовано:** Web-панель администратора (отчёты по
  посещаемости).

## Жизненный цикл AttendanceLog

Каждая запись — одна сессия пребывания сотрудника в зоне. Сессия
**открыта** пока `ended_at IS NULL`, **закрыта** после проставления
`ended_at` и пересчёта `duration_seconds`.

### Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | bigint PK | Идентификатор |
| `employee_id` | bigint FK | Сотрудник (ON DELETE CASCADE) |
| `zone_id` | bigint FK | Зона (ON DELETE RESTRICT) |
| `started_at` | timestamptz | Начало сессии |
| `ended_at` | timestamptz NULL | Конец сессии (NULL = открыта) |
| `last_seen_at` | timestamptz | Последний классификации в этой зоне |
| `duration_seconds` | int NULL | Длительность (заполняется при закрытии) |
| `status` | enum | `present` / `late` / `absent` / `overtime` |

### Индексы

- `ix_attendance_logs_employee_started` (`employee_id`, `started_at`) —
  для отчётов «логи сотрудника за период».
- `ix_attendance_logs_open_sessions` partial `WHERE ended_at IS NULL` —
  для быстрого поиска открытой сессии (запрос на каждом `/classify`).
- `ix_attendance_logs_zone` — для отчётов по зонам.

### CHECK-constraints

- `ended_after_started`: `ended_at IS NULL OR ended_at > started_at`.
- `duration_non_negative`: `duration_seconds IS NULL OR duration_seconds >= 0`.

## RecordAttendanceUseCase: 5-веточная логика

При каждом успешном `POST /api/v1/positioning/classify` запускается
use case `RecordAttendanceUseCase` (use case вызывается в
presentation-слое — в обработчике `/classify` после успешной
классификации, см. `app/presentation/api/v1/positioning.py`).

Алгоритм (упрощённо):

```
INPUT: employee_id=E, zone_id=Z, zone_type=T, now=N

open = AttendanceRepo.get_open_session_for_employee(E)

IF open IS NULL:
    OPEN new session (started_at=N, last_seen_at=N, zone_id=Z, status=compute_on_open)
    RETURN

inactivity = N - open.last_seen_at

IF open.zone_id == Z:
    IF inactivity <= INACTIVITY_TIMEOUT:
        EXTEND open (last_seen_at=N)
        RETURN
    ELSE:
        # таймаут в той же зоне
        CLOSE open (ended_at=open.last_seen_at, status=compute_final)
        OPEN new session (started_at=N, last_seen_at=N)
        RETURN

# другая зона
CLOSE open (ended_at=N, status=compute_final)
OPEN new session (started_at=N, last_seen_at=N, zone_id=Z)
```

### Edge case: timeout сразу после открытия

Если сессия открыта и сразу после неё прошло больше INACTIVITY_TIMEOUT
без единого `extend` — `last_seen_at == started_at`, и попытка закрыть
с `ended_at = last_seen_at` нарушила бы CHECK-constraint
`ended_at > started_at`. Use case **клампит** `ended_at` до
`started_at + 1µs` (`duration_seconds = 0`).

### Inactivity-timeout

Настройка через env-переменную:

```
ATTENDANCE_INACTIVITY_TIMEOUT_SECONDS=1800
```

По умолчанию 30 минут. Допустимый диапазон: 60..86400 секунд (1 минута
.. 24 часа). Меньше 1 минуты — слишком чувствительно (типичный mobile
WorkManager-цикл), больше 24 часов — нелогично для рабочего дня.

## Расчёт статусов

Реализовано в `app/domain/attendance/services.py`:

### При открытии сессии — `compute_status_on_open`

```
IF zone_type != WORKPLACE: return PRESENT  # учёт времени только в рабочих зонах
IF schedule_start IS NULL: return PRESENT  # графика нет
IF started_at.time() > schedule_start: return LATE
ELSE: return PRESENT
```

### При закрытии сессии — `compute_final_status`

```
IF schedule_end IS NULL: return current_status  # графика нет
IF ended_at.time() > schedule_end: return OVERTIME  # повышение статуса
ELSE: return current_status
```

⚠️ Сравнение по `time()` (часть-минута без даты) предполагает, что
рабочий день не пересекает полночь. Для night shifts (например, 22:00 →
06:00) логику нужно расширить — пока вне MVP.

## REST API

### `GET /api/v1/attendance` — список сессий

Параметры (все опциональны кроме `limit/offset`):

| Параметр | Тип | Описание |
|----------|-----|----------|
| `employee_id` | int | Фильтр по сотруднику |
| `zone_id` | int | Фильтр по зоне |
| `status` | enum | `present` / `late` / `absent` / `overtime` |
| `started_from` | datetime | Нижняя граница `started_at` (timezone-aware) |
| `started_to` | datetime | Верхняя граница `started_at` |
| `limit` | int (1-200) | По умолчанию 50 |
| `offset` | int (≥0) | По умолчанию 0 |

**Пример:**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/attendance?employee_id=42&started_from=2026-05-01T00:00:00%2B00:00&started_to=2026-05-31T23:59:59%2B00:00"
```

**Ответ (200):**

```json
{
  "items": [
    {
      "id": 123,
      "employee_id": 42,
      "zone_id": 7,
      "started_at": "2026-05-02T09:00:00+00:00",
      "ended_at": "2026-05-02T18:15:00+00:00",
      "last_seen_at": "2026-05-02T18:15:00+00:00",
      "duration_seconds": 33300,
      "status": "overtime"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### `GET /api/v1/attendance/summary` — агрегация по периоду

Параметры (все обязательны):

| Параметр | Тип | Описание |
|----------|-----|----------|
| `employee_id` | int | Сотрудник |
| `from` | datetime | Начало периода (timezone-aware) |
| `to` | datetime | Конец периода (timezone-aware, строго позже `from`) |

**Пример:**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/attendance/summary?employee_id=42&from=2026-05-01T00:00:00%2B00:00&to=2026-05-31T23:59:59%2B00:00"
```

**Ответ (200):**

```json
{
  "employee_id": 42,
  "period_from": "2026-05-01T00:00:00+00:00",
  "period_to": "2026-05-31T23:59:59+00:00",
  "work_hours_total": 165.5,
  "lateness_count": 3,
  "overtime_seconds_total": 18000,
  "sessions_count": 22
}
```

**Семантика метрик:**

- `work_hours_total`: сумма `duration_seconds / 3600` по сессиям, у
  которых `zone.type = workplace` И `ended_at IS NOT NULL`. Открытые
  сессии не учитываются.
- `lateness_count`: число сессий со статусом `late` (включая открытые —
  статус известен сразу при открытии).
- `overtime_seconds_total`: сумма `duration_seconds` по закрытым
  сессиям со статусом `overtime`. Упрощённо — считается вся
  длительность OVERTIME-сессии, не только часть после `schedule_end`.
  Точный расчёт оставлен на следующую итерацию.
- `sessions_count`: все сессии в периоде, включая открытые.

## Доступ и авторизация

| Эндпоинт | Admin | Employee |
|----------|-------|----------|
| `GET /attendance` | OK (любой `employee_id` или без фильтра) | OK (только свой `employee_id`; подставляется автоматически если не указан) |
| `GET /attendance/summary` | OK (любой `employee_id`) | OK только если `employee_id == current_user.id` |

При попытке employee запросить чужие данные — `403 Forbidden` с
`code=attendance_self_only`. Self-only проверка делается на уровне use
case (`ListAttendanceUseCase`/`ComputeAttendanceSummaryUseCase`), не
на уровне роутера.

## Лимиты MVP

- Открытые сессии исключены из `work_hours_total` и
  `overtime_seconds_total` — длительность пока неизвестна.
- `overtime_seconds_total` считает всю длительность OVERTIME-сессии,
  а не только часть после `schedule_end`.
- Сессии, пересекающие полночь, могут получить неверный `overtime`
  статус из-за сравнения по `time()` без даты.
- Inactivity-timeout — глобальный (один на всю систему), не
  настраиваемый per-employee.
- При открытии сессии и срабатывании timeout без единого `extend`
  длительность — 0 секунд (клампинг до 1µs для соблюдения CHECK).

Эти ограничения не критичны для MVP. Доработки — в следующей итерации.

## Тесты

- **Unit:** `backend/tests/unit/application/test_record_attendance.py`
  (9 тестов) — покрывает все 5 веток + статусы + ошибки.
- **Unit:** `backend/tests/unit/application/test_list_attendance.py`
  (4 теста) — фильтры + self-only.
- **Unit:** `backend/tests/unit/application/test_compute_attendance_summary.py`
  (5 тестов) — агрегация + исключение открытых сессий + self-only.
- **Integration:** `backend/tests/integration/api/test_attendance.py`
  (6 тестов) — `/classify` авто-создаёт `AttendanceLog`, смена зоны
  закрывает сессию, employee 403, admin sees all, summary считает
  work_hours, 401 без токена.

Запуск:

```bash
cd backend
pytest tests/unit/application/test_record_attendance.py \
       tests/unit/application/test_list_attendance.py \
       tests/unit/application/test_compute_attendance_summary.py \
       tests/integration/api/test_attendance.py -v
```

Integration-тесты требуют Docker (для testcontainers PostgreSQL) или
переменной `TEST_DATABASE_URL`.
