"""Эндпоинты приёма и просмотра радиоотпечатков.

POST /api/v1/fingerprints — любой авторизованный (mobile-приложение
сотрудника шлёт live-замеры). Сервер автоматически проставляет
employee_id=current_user.id, is_calibration=False, zone_id=NULL
(классификация — задача следующей вехи ML).

GET-операции — admin-only (для отладки и анализа).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.application.radiomap.list_fingerprints import (
    GetFingerprintQuery,
    GetFingerprintUseCase,
    ListFingerprintsQuery,
    ListFingerprintsUseCase,
)
from app.application.radiomap.submit_fingerprint import (
    SubmitFingerprintCommand,
    SubmitFingerprintUseCase,
)
from app.application.radiomap.submit_fingerprints_batch import (
    SubmitFingerprintsBatchCommand,
    SubmitFingerprintsBatchUseCase,
)
from app.core.logging import get_logger
from app.domain.employees.entities import Employee, Role
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import RSSIVector
from app.presentation.dependencies import (
    get_current_user,
    get_fingerprint_use_case,
    get_list_fingerprints_use_case,
    get_submit_fingerprint_use_case,
    get_submit_fingerprints_batch_use_case,
    require_role,
)
from app.presentation.schemas.radiomap import (
    BulkAcceptedItem,
    BulkRejectedItem,
    FingerprintBulkSubmitRequest,
    FingerprintBulkSubmitResponse,
    FingerprintResponse,
    FingerprintsPageResponse,
    FingerprintSubmitRequest,
)

log = get_logger(__name__)

router = APIRouter(prefix="/fingerprints", tags=["fingerprints"])


def _to_response(fp: Fingerprint) -> FingerprintResponse:
    return FingerprintResponse(
        id=fp.id,
        employee_id=fp.employee_id,
        zone_id=fp.zone_id,
        is_calibration=fp.is_calibration,
        captured_at=fp.captured_at,
        device_id=fp.device_id,
        rssi_vector=fp.rssi_vector.to_dict(),
        sample_count=fp.sample_count,
    )


@router.post(
    "",
    response_model=FingerprintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Принять live-радиоотпечаток (auth)",
)
async def submit_fingerprint(
    payload: FingerprintSubmitRequest,
    current_user: Employee = Depends(get_current_user),
    use_case: SubmitFingerprintUseCase = Depends(get_submit_fingerprint_use_case),
) -> FingerprintResponse:
    log.debug(
        "[fingerprints.endpoint.submit] start",
        employee_id=current_user.id,
        ap_count=len(payload.rssi_vector),
    )

    cmd = SubmitFingerprintCommand(
        employee_id=current_user.id,
        captured_at=payload.captured_at,
        device_id=payload.device_id,
        rssi_vector=RSSIVector(payload.rssi_vector),
        sample_count=payload.sample_count,
    )
    result = await use_case.execute(cmd)
    return _to_response(result)


@router.post(
    "/batch",
    response_model=FingerprintBulkSubmitResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk-приём live-отпечатков (auth)",
)
async def submit_fingerprints_batch(
    payload: FingerprintBulkSubmitRequest,
    current_user: Employee = Depends(get_current_user),
    use_case: SubmitFingerprintsBatchUseCase = Depends(
        get_submit_fingerprints_batch_use_case
    ),
) -> FingerprintBulkSubmitResponse:
    log.debug(
        "[fingerprints.endpoint.batch] start",
        employee_id=current_user.id,
        items_count=len(payload.items),
    )

    commands = [
        SubmitFingerprintCommand(
            employee_id=current_user.id,
            captured_at=item.captured_at,
            device_id=item.device_id,
            rssi_vector=RSSIVector(item.rssi_vector),
            sample_count=item.sample_count,
        )
        for item in payload.items
    ]
    result = await use_case.execute(
        SubmitFingerprintsBatchCommand(
            employee_id=current_user.id,
            items=commands,
        )
    )

    log.info(
        "[fingerprints.endpoint.batch] done",
        employee_id=current_user.id,
        accepted_count=len(result.accepted),
        rejected_count=len(result.rejected),
    )
    return FingerprintBulkSubmitResponse(
        accepted=[
            BulkAcceptedItem(index=a.index, fingerprint=_to_response(a.fingerprint))
            for a in result.accepted
        ],
        rejected=[
            BulkRejectedItem(index=r.index, code=r.code, message=r.message)
            for r in result.rejected
        ],
        accepted_count=len(result.accepted),
        rejected_count=len(result.rejected),
    )


@router.get(
    "",
    response_model=FingerprintsPageResponse,
    summary="Список радиоотпечатков (admin)",
)
async def list_fingerprints(
    employee_id: int | None = Query(default=None),
    zone_id: int | None = Query(default=None),
    is_calibration: bool | None = Query(default=None),
    captured_from: datetime | None = Query(
        default=None,
        description="Нижняя граница captured_at (timezone-aware)",
    ),
    captured_to: datetime | None = Query(
        default=None,
        description="Верхняя граница captured_at (timezone-aware)",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: Employee = Depends(require_role(Role.ADMIN)),
    use_case: ListFingerprintsUseCase = Depends(get_list_fingerprints_use_case),
) -> FingerprintsPageResponse:
    log.debug(
        "[fingerprints.endpoint.list] start",
        employee_id=employee_id,
        zone_id=zone_id,
        is_calibration=is_calibration,
        limit=limit,
        offset=offset,
    )

    page = await use_case.execute(
        ListFingerprintsQuery(
            employee_id=employee_id,
            zone_id=zone_id,
            is_calibration=is_calibration,
            captured_from=captured_from,
            captured_to=captured_to,
            limit=limit,
            offset=offset,
        )
    )
    return FingerprintsPageResponse(
        items=[_to_response(fp) for fp in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{fingerprint_id}",
    response_model=FingerprintResponse,
    summary="Получить отпечаток по id (admin)",
)
async def get_fingerprint(
    fingerprint_id: int,
    _: Employee = Depends(require_role(Role.ADMIN)),
    use_case: GetFingerprintUseCase = Depends(get_fingerprint_use_case),
) -> FingerprintResponse:
    log.debug(
        "[fingerprints.endpoint.get] start", fingerprint_id=fingerprint_id
    )
    fp = await use_case.execute(GetFingerprintQuery(fingerprint_id=fingerprint_id))
    return _to_response(fp)
