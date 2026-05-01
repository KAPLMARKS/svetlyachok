"""Доменная сущность `AttendanceLog`.

Domain-уровень не знает об ORM — `AttendanceLog` живёт независимо
от SQLAlchemy. Маппер ORM↔domain — забота infrastructure-репозитория.

Каждая запись соответствует одной «сессии» нахождения сотрудника в
зоне: от первого появления до перехода в другую зону или срабатывания
inactivity-timeout. Открытая сессия — `ended_at IS None`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from app.domain.attendance.value_objects import AttendanceStatus
from app.domain.shared.exceptions import ValidationError


@dataclass(frozen=True)
class AttendanceLog:
    """Запись о пребывании сотрудника в зоне.

    Жизненный цикл:

    - **Открытая** (`ended_at is None`): сотрудник продолжает быть
      замеченным в зоне; `last_seen_at` обновляется на каждом классификации.
    - **Закрытая** (`ended_at is not None`): сессия завершена, `duration_seconds`
      посчитан как `(ended_at - started_at).total_seconds()`.

    Frozen — после создания не мутируется; обновление через `extend`,
    `close`, или `replace`.
    """

    id: int
    employee_id: int
    zone_id: int
    started_at: datetime
    ended_at: datetime | None
    last_seen_at: datetime
    duration_seconds: int | None
    status: AttendanceStatus

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None:
            raise ValidationError(
                code="attendance_started_at_must_be_timezone_aware",
                message="started_at обязан быть timezone-aware (предпочтительно UTC)",
            )
        if self.last_seen_at.tzinfo is None:
            raise ValidationError(
                code="attendance_last_seen_at_must_be_timezone_aware",
                message="last_seen_at обязан быть timezone-aware (предпочтительно UTC)",
            )
        if self.ended_at is not None:
            if self.ended_at.tzinfo is None:
                raise ValidationError(
                    code="attendance_ended_at_must_be_timezone_aware",
                    message="ended_at обязан быть timezone-aware (предпочтительно UTC)",
                )
            if self.ended_at <= self.started_at:
                raise ValidationError(
                    code="attendance_ended_before_started",
                    message=(
                        f"ended_at ({self.ended_at}) должен быть строго позже "
                        f"started_at ({self.started_at})"
                    ),
                )
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValidationError(
                code="attendance_duration_negative",
                message=f"duration_seconds должен быть >= 0, получено {self.duration_seconds}",
            )
        if self.last_seen_at < self.started_at:
            raise ValidationError(
                code="attendance_last_seen_before_started",
                message=(
                    f"last_seen_at ({self.last_seen_at}) не может быть раньше "
                    f"started_at ({self.started_at})"
                ),
            )

    @property
    def is_open(self) -> bool:
        """Сессия ещё не закрыта (сотрудник продолжает быть в зоне)."""
        return self.ended_at is None

    def extend(self, now: datetime) -> AttendanceLog:
        """Возвращает копию с обновлённым `last_seen_at = now`.

        Используется RecordAttendanceUseCase, когда сотрудник снова замечен
        в той же зоне в пределах inactivity-timeout — продлевает открытую сессию.
        """
        return replace(self, last_seen_at=now)

    def close(
        self,
        ended_at: datetime,
        status: AttendanceStatus,
    ) -> AttendanceLog:
        """Возвращает копию с проставленным `ended_at`, `duration_seconds`
        и финальным статусом.

        Args:
            ended_at: момент закрытия сессии (timezone-aware).
            status: финальный статус (например, OVERTIME при закрытии после
                schedule_end).
        """
        if ended_at.tzinfo is None:
            raise ValidationError(
                code="attendance_ended_at_must_be_timezone_aware",
                message="ended_at обязан быть timezone-aware",
            )
        duration = int((ended_at - self.started_at).total_seconds())
        return replace(
            self,
            ended_at=ended_at,
            duration_seconds=duration,
            status=status,
        )
