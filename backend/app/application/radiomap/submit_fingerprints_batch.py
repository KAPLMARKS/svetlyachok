"""Use case bulk-приёма live-радиоотпечатков от мобильного клиента.

Mobile (Flutter + WorkManager) копит отпечатки в sqflite-кэше при
отсутствии сети и шлёт пачкой при возвращении сети. Этот use case
обрабатывает каждый item независимо: один невалидный отпечаток не
валит весь батч.

Семантика — partial success:
* `accepted` — успешно сохранённые отпечатки с их index'ами в
  исходном массиве (mobile удалит их из sqflite).
* `rejected` — отклонённые с код/сообщением (mobile решает по коду:
  удалять как нерешаемую ошибку, например `captured_at_too_old`, или
  оставлять для retry).

Композиция, а не дублирование: внутри вызывается
`SubmitFingerprintUseCase.execute()` per item, чтобы валидация и
бизнес-правила были одни и те же.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.radiomap.submit_fingerprint import (
    SubmitFingerprintCommand,
    SubmitFingerprintUseCase,
)
from app.core.logging import get_logger
from app.domain.radiomap.entities import Fingerprint
from app.domain.shared.exceptions import AppError

log = get_logger(__name__)


@dataclass(frozen=True)
class SubmitFingerprintsBatchCommand:
    employee_id: int
    items: list[SubmitFingerprintCommand]


@dataclass(frozen=True)
class BatchAccepted:
    index: int
    fingerprint: Fingerprint


@dataclass(frozen=True)
class BatchRejected:
    index: int
    code: str
    message: str


@dataclass(frozen=True)
class BatchResult:
    accepted: list[BatchAccepted]
    rejected: list[BatchRejected]


class SubmitFingerprintsBatchUseCase:
    """Bulk-приём отпечатков с partial success.

    Зависит не от репозитория, а от `SubmitFingerprintUseCase` —
    переиспользуем валидацию и логи single-item варианта.
    """

    def __init__(self, submit_use_case: SubmitFingerprintUseCase) -> None:
        self._submit = submit_use_case

    async def execute(self, cmd: SubmitFingerprintsBatchCommand) -> BatchResult:
        log.debug(
            "[fingerprints.batch.execute] start",
            employee_id=cmd.employee_id,
            items_count=len(cmd.items),
        )

        accepted: list[BatchAccepted] = []
        rejected: list[BatchRejected] = []

        for index, item in enumerate(cmd.items):
            # employee_id командой передан с уровня роутера на основании
            # current_user — проверяем инвариант, чтобы случайно не
            # сохранить от чужого имени.
            assert item.employee_id == cmd.employee_id, (
                "employee_id у item должен совпадать с batch employee_id"
            )
            try:
                fingerprint = await self._submit.execute(item)
            except AppError as exc:
                log.warning(
                    "[fingerprints.batch.execute] item_rejected",
                    employee_id=cmd.employee_id,
                    index=index,
                    code=exc.code,
                    message=exc.message,
                )
                rejected.append(
                    BatchRejected(index=index, code=exc.code, message=exc.message)
                )
                continue

            accepted.append(BatchAccepted(index=index, fingerprint=fingerprint))

        log.info(
            "[fingerprints.batch.execute] done",
            employee_id=cmd.employee_id,
            accepted_count=len(accepted),
            rejected_count=len(rejected),
        )
        return BatchResult(accepted=accepted, rejected=rejected)
