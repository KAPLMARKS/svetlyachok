"""Value objects модуля attendance.

`AttendanceStatus` — статус сессии присутствия. Зеркалит ORM-enum
`infrastructure/db/orm/attendance.py:AttendanceStatus` строка-в-строку,
но импортов из infrastructure нет (Clean Architecture).

`WorkInterval` — интервал работы (period_from/to для фильтров и summary).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.shared.exceptions import ValidationError


class AttendanceStatus(str, enum.Enum):
    """Статус сессии присутствия.

    - `PRESENT` — нормальное присутствие в рабочей зоне в графике.
    - `LATE` — приход в рабочую зону позже `Employee.schedule_start`.
    - `OVERTIME` — присутствие после `Employee.schedule_end`.
    - `ABSENT` — резервный (используется только в агрегациях/отчётах,
      в open/close-логике сессий не появляется).
    """

    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"
    OVERTIME = "overtime"


@dataclass(frozen=True)
class WorkInterval:
    """Закрытый интервал `[start; end]` для фильтров и агрегаций.

    Используется в use cases `ListAttendance` и `ComputeAttendanceSummary`
    как тип-обёртка над парой timezone-aware datetime'ов: гарантирует
    непустой и упорядоченный диапазон уже на доменном уровне.
    """

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValidationError(
                code="work_interval_must_be_timezone_aware",
                message="WorkInterval.start/end обязаны быть timezone-aware",
            )
        if self.end <= self.start:
            raise ValidationError(
                code="work_interval_end_before_start",
                message=f"WorkInterval.end ({self.end}) должен быть строго позже start ({self.start})",
            )

    @property
    def duration(self) -> timedelta:
        """Продолжительность интервала."""
        return self.end - self.start
