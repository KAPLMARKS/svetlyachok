"""Доменные сервисы модуля attendance.

Чистые функции расчёта статуса сессии присутствия. Никакой инфраструктуры —
только domain-типы (`AttendanceStatus`, `ZoneType`) + stdlib.

Алгоритм:

- При **открытии** сессии (`compute_status_on_open`): сравнить
  `started_at.time()` с `Employee.schedule_start`. Если позже — `LATE`,
  иначе — `PRESENT`. Применимо только к рабочим зонам (`workplace`);
  для прочих зон возвращается `PRESENT` (присутствие, но не учитываемое
  в работе).

- При **закрытии** сессии (`compute_final_status`): если `ended_at.time()`
  позже `Employee.schedule_end`, статус повышается до `OVERTIME`. В
  остальных случаях оставляем тот, что был при открытии.

Если у сотрудника нет графика (`schedule_start is None` или
`schedule_end is None`), late/overtime не вычисляется — всегда
возвращается тот же статус.
"""

from __future__ import annotations

from datetime import datetime, time

from app.core.logging import get_logger
from app.domain.attendance.value_objects import AttendanceStatus
from app.domain.zones.entities import ZoneType

log = get_logger(__name__)


def compute_status_on_open(
    started_at: datetime,
    zone_type: ZoneType,
    schedule_start: time | None,
) -> AttendanceStatus:
    """Возвращает статус сессии в момент её открытия.

    - Не-рабочая зона (`corridor`, `meeting_room`, `outside_office`) →
      `PRESENT` без проверки графика.
    - Рабочая зона (`workplace`):
        - Если `schedule_start is None` → `PRESENT` (график не задан).
        - Если `started_at.time() > schedule_start` → `LATE`.
        - Иначе → `PRESENT`.
    """
    log.debug(
        "[attendance.compute_status_on_open] start",
        started_at=started_at.isoformat(),
        zone_type=zone_type.value,
        schedule_start=schedule_start.isoformat() if schedule_start else None,
    )

    if zone_type is not ZoneType.WORKPLACE:
        log.debug(
            "[attendance.compute_status_on_open] non-workplace zone → present",
            zone_type=zone_type.value,
        )
        return AttendanceStatus.PRESENT

    if schedule_start is None:
        log.debug("[attendance.compute_status_on_open] no schedule → present")
        return AttendanceStatus.PRESENT

    started_time = started_at.time()
    if started_time > schedule_start:
        log.debug(
            "[attendance.compute_status_on_open] started after schedule_start → late",
            started_time=started_time.isoformat(),
            schedule_start=schedule_start.isoformat(),
        )
        return AttendanceStatus.LATE

    log.debug("[attendance.compute_status_on_open] within schedule → present")
    return AttendanceStatus.PRESENT


def compute_final_status(
    started_at: datetime,
    ended_at: datetime,
    current_status: AttendanceStatus,
    schedule_end: time | None,
) -> AttendanceStatus:
    """Возвращает финальный статус сессии при её закрытии.

    Сравнивает `ended_at.time()` с `schedule_end` и повышает статус
    до `OVERTIME`, если конец сессии позже расписания. В противном
    случае возвращает `current_status` без изменений.

    Замечание: если сессия пересекает полночь (started_at.date()
    отличается от ended_at.date()), сравнение по времени суток может
    дать ложные результаты. Для MVP считаем, что рабочий день не
    пересекает полночь.
    """
    log.debug(
        "[attendance.compute_final_status] start",
        started_at=started_at.isoformat(),
        ended_at=ended_at.isoformat(),
        current_status=current_status.value,
        schedule_end=schedule_end.isoformat() if schedule_end else None,
    )

    if schedule_end is None:
        log.debug("[attendance.compute_final_status] no schedule_end → keep current")
        return current_status

    ended_time = ended_at.time()
    if ended_time > schedule_end:
        log.debug(
            "[attendance.compute_final_status] ended after schedule_end → overtime",
            ended_time=ended_time.isoformat(),
            schedule_end=schedule_end.isoformat(),
        )
        return AttendanceStatus.OVERTIME

    log.debug("[attendance.compute_final_status] within schedule → keep current")
    return current_status
