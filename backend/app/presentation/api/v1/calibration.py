"""Эндпоинты управления калибровочной радиокартой.

POST/DELETE — admin-only.
GET — любой авторизованный (mobile/web показывает калибровочные точки
в UI, например, при отображении радиокарты или выборе зоны).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.application.radiomap.calibrate_radiomap import (
    CreateCalibrationPointCommand,
    CreateCalibrationPointUseCase,
)
from app.application.radiomap.delete_calibration_point import (
    DeleteCalibrationPointCommand,
    DeleteCalibrationPointUseCase,
)
from app.application.radiomap.list_calibration_points import (
    ListCalibrationPointsQuery,
    ListCalibrationPointsUseCase,
)
from app.core.logging import get_logger
from app.domain.employees.entities import Employee, Role
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.value_objects import RSSIVector
from app.presentation.dependencies import (
    get_create_calibration_point_use_case,
    get_current_user,
    get_delete_calibration_point_use_case,
    get_list_calibration_points_use_case,
    require_role,
)
from app.presentation.schemas.radiomap import (
    CalibrationPointCreateRequest,
    FingerprintResponse,
    FingerprintsPageResponse,
)

log = get_logger(__name__)

router = APIRouter(prefix="/calibration", tags=["calibration"])


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
    "/points",
    response_model=FingerprintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать калибровочную точку (admin)",
)
async def create_calibration_point(
    payload: CalibrationPointCreateRequest,
    current_user: Employee = Depends(require_role(Role.ADMIN)),
    use_case: CreateCalibrationPointUseCase = Depends(
        get_create_calibration_point_use_case
    ),
) -> FingerprintResponse:
    log.debug(
        "[calibration.endpoint.create] start",
        zone_id=payload.zone_id,
        admin_id=current_user.id,
    )
    cmd = CreateCalibrationPointCommand(
        zone_id=payload.zone_id,
        captured_at=payload.captured_at,
        rssi_vector=RSSIVector(payload.rssi_vector),
        sample_count=payload.sample_count,
        device_id=payload.device_id,
        employee_id=current_user.id,
    )
    result = await use_case.execute(cmd)
    return _to_response(result)


@router.get(
    "/points",
    response_model=FingerprintsPageResponse,
    summary="Список калибровочных точек (любой авторизованный)",
)
async def list_calibration_points(
    zone_id: int | None = Query(default=None, description="Фильтр по зоне"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: Employee = Depends(get_current_user),
    use_case: ListCalibrationPointsUseCase = Depends(
        get_list_calibration_points_use_case
    ),
) -> FingerprintsPageResponse:
    log.debug(
        "[calibration.endpoint.list] start",
        zone_id=zone_id,
        limit=limit,
        offset=offset,
    )
    page = await use_case.execute(
        ListCalibrationPointsQuery(zone_id=zone_id, limit=limit, offset=offset)
    )
    return FingerprintsPageResponse(
        items=[_to_response(fp) for fp in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.delete(
    "/points/{fingerprint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить калибровочную точку (admin)",
)
async def delete_calibration_point(
    fingerprint_id: int,
    _: Employee = Depends(require_role(Role.ADMIN)),
    use_case: DeleteCalibrationPointUseCase = Depends(
        get_delete_calibration_point_use_case
    ),
) -> Response:
    log.debug(
        "[calibration.endpoint.delete] start", fingerprint_id=fingerprint_id
    )
    await use_case.execute(
        DeleteCalibrationPointCommand(fingerprint_id=fingerprint_id)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
