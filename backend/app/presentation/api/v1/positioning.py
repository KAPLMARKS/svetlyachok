"""Эндпоинт классификации позиции по RSSI-вектору.

Любой авторизованный сотрудник может запросить классификацию (mobile
шлёт текущий RSSI и получает зону).

Для admin-инструментов (фоновое переобучение, A/B-сравнение
классификаторов) на следующих вехах добавим отдельные эндпоинты.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.positioning.classify_location import (
    ClassifyLocationCommand,
    ClassifyLocationUseCase,
)
from app.core.logging import get_logger
from app.domain.employees.entities import Employee
from app.domain.radiomap.value_objects import RSSIVector
from app.presentation.dependencies import (
    get_classify_location_use_case,
    get_current_user,
)
from app.presentation.schemas.positioning import ClassifyRequest, ClassifyResponse

log = get_logger(__name__)

router = APIRouter(prefix="/positioning", tags=["positioning"])


@router.post(
    "/classify",
    response_model=ClassifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Классифицировать позицию по RSSI-вектору",
    description=(
        "Принимает RSSI-вектор (BSSID → dBm), возвращает предсказанную "
        "зону и confidence. При первом запросе классификатор lazy-обучается "
        "на калибровочных данных. Если калибровка отсутствует или "
        "недостаточна — 503 classifier_not_ready."
    ),
)
async def classify_location(
    payload: ClassifyRequest,
    current_user: Employee = Depends(get_current_user),
    use_case: ClassifyLocationUseCase = Depends(get_classify_location_use_case),
) -> ClassifyResponse:
    log.debug(
        "[positioning.endpoint.classify] start",
        employee_id=current_user.id,
        ap_count=len(payload.rssi_vector),
    )

    cmd = ClassifyLocationCommand(
        rssi_vector=RSSIVector(payload.rssi_vector),
        employee_id=current_user.id,
    )
    result = await use_case.execute(cmd)

    return ClassifyResponse(
        zone_id=result.zone_id,
        zone_type=result.zone_type.value,
        confidence=float(result.confidence),
        classifier_name=result.classifier_name,
    )
