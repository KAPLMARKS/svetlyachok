"""Use case приёма live-радиоотпечатка от устройства сотрудника.

Live-отпечаток сохраняется с `is_calibration=False` и без `zone_id` —
классификация (и создание AttendanceLog) — на следующей вехе ML.

Anti-fraud по `captured_at`: отбраковываем запросы «из будущего»
(clock skew или manipulation) и слишком старые (несвежие после
длительного офлайна — для классификации бесполезны).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.logging import get_logger
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.repositories import FingerprintRepository
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.shared.exceptions import ValidationError

log = get_logger(__name__)

# Допустимое окно «в будущем» — clock skew мобильника может быть до пары
# минут; даём запас в 5 минут. Больше — точно битые данные.
_MAX_FUTURE_SKEW = timedelta(minutes=5)

# Максимальный возраст отпечатка. Mobile может накопить кэш в офлайне,
# но через неделю данные несвежие — за это время AP могли поменяться.
_MAX_AGE = timedelta(days=7)


@dataclass(frozen=True)
class SubmitFingerprintCommand:
    employee_id: int
    captured_at: datetime
    device_id: str | None
    rssi_vector: RSSIVector
    sample_count: int


class SubmitFingerprintUseCase:
    def __init__(self, fingerprint_repo: FingerprintRepository) -> None:
        self._repo = fingerprint_repo

    async def execute(self, cmd: SubmitFingerprintCommand) -> Fingerprint:
        log.debug(
            "[radiomap.submit.execute] start",
            employee_id=cmd.employee_id,
            ap_count=len(cmd.rssi_vector),
            sample_count=cmd.sample_count,
        )

        now = datetime.now(tz=UTC)
        if cmd.captured_at > now + _MAX_FUTURE_SKEW:
            log.warning(
                "[radiomap.submit.execute] fail",
                reason="captured_at_in_future",
                employee_id=cmd.employee_id,
                drift_seconds=(cmd.captured_at - now).total_seconds(),
            )
            raise ValidationError(
                code="captured_at_in_future",
                message=(
                    "captured_at не может быть слишком далеко в будущем "
                    f"(>{int(_MAX_FUTURE_SKEW.total_seconds())} сек.)"
                ),
            )
        if cmd.captured_at < now - _MAX_AGE:
            log.warning(
                "[radiomap.submit.execute] fail",
                reason="captured_at_too_old",
                employee_id=cmd.employee_id,
                age_seconds=(now - cmd.captured_at).total_seconds(),
            )
            raise ValidationError(
                code="captured_at_too_old",
                message=(
                    f"captured_at слишком старый (>{_MAX_AGE.days} дней назад). "
                    "Несвежие отпечатки бесполезны для классификации."
                ),
            )

        fingerprint = Fingerprint(
            id=0,
            employee_id=cmd.employee_id,
            zone_id=None,
            is_calibration=False,
            captured_at=cmd.captured_at,
            device_id=cmd.device_id,
            rssi_vector=cmd.rssi_vector,
            sample_count=cmd.sample_count,
        )
        created = await self._repo.add(fingerprint)

        log.info(
            "[radiomap.submit.execute] success",
            employee_id=cmd.employee_id,
            fingerprint_id=created.id,
            ap_count=len(cmd.rssi_vector),
        )
        return created
