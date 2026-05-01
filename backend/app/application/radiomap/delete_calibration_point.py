"""Use case удаления калибровочной точки (admin).

Защищается от случайного удаления live-отпечатка через эндпоинт
калибровки: если переданный id принадлежит не калибровочному
отпечатку — ValidationError(not_a_calibration_point).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.domain.radiomap.repositories import FingerprintRepository
from app.domain.shared.exceptions import NotFoundError, ValidationError

log = get_logger(__name__)


@dataclass(frozen=True)
class DeleteCalibrationPointCommand:
    fingerprint_id: int


class DeleteCalibrationPointUseCase:
    def __init__(self, fingerprint_repo: FingerprintRepository) -> None:
        self._repo = fingerprint_repo

    async def execute(self, cmd: DeleteCalibrationPointCommand) -> None:
        log.debug(
            "[radiomap.delete_calibration.execute] start",
            fingerprint_id=cmd.fingerprint_id,
        )

        existing = await self._repo.get_by_id(cmd.fingerprint_id)
        if existing is None:
            log.warning(
                "[radiomap.delete_calibration.execute] fail",
                reason="not_found",
                fingerprint_id=cmd.fingerprint_id,
            )
            raise NotFoundError(
                code="fingerprint_not_found",
                message=f"Отпечаток с id={cmd.fingerprint_id} не найден",
            )

        if not existing.is_calibration:
            log.warning(
                "[radiomap.delete_calibration.execute] fail",
                reason="not_a_calibration_point",
                fingerprint_id=cmd.fingerprint_id,
            )
            raise ValidationError(
                code="not_a_calibration_point",
                message=(
                    "Этот эндпоинт удаляет только калибровочные отпечатки. "
                    "Live-отпечатки удаляются администратором через общий "
                    "эндпоинт /api/v1/fingerprints/{id} (если потребуется)."
                ),
            )

        await self._repo.delete_by_id(cmd.fingerprint_id)
        log.info(
            "[radiomap.delete_calibration.execute] success",
            fingerprint_id=cmd.fingerprint_id,
        )
