"""Эндпоинт классификации позиции по RSSI-вектору.

Любой авторизованный сотрудник может запросить классификацию (mobile
шлёт текущий RSSI и получает зону).

После успешной классификации эндпоинт также фиксирует AttendanceLog
через `RecordAttendanceUseCase` (открытие/продление/закрытие сессии
по логике inactivity-timeout). Если запись посещаемости падает — это
не должно ломать ответ classify: ошибка логируется на WARNING, но
клиент всё равно получает результат классификации.

Для admin-инструментов (фоновое переобучение, A/B-сравнение
классификаторов) на следующих вехах добавим отдельные эндпоинты.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status

from app.application.attendance.record_attendance import (
    RecordAttendanceCommand,
    RecordAttendanceUseCase,
)
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
    get_record_attendance_use_case,
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
        "недостаточна — 503 classifier_not_ready. После успешной "
        "классификации автоматически создаётся/продлевается AttendanceLog "
        "(см. /api/v1/attendance)."
    ),
)
async def classify_location(
    payload: ClassifyRequest,
    current_user: Employee = Depends(get_current_user),
    use_case: ClassifyLocationUseCase = Depends(get_classify_location_use_case),
    record_attendance_use_case: RecordAttendanceUseCase = Depends(
        get_record_attendance_use_case
    ),
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

    # Авто-создание/продление AttendanceLog. Падение здесь не должно
    # ломать ответ /classify — клиент всё равно ждёт зону. Логируем как
    # WARNING с traceback'ом, чтобы оператор увидел проблему.
    try:
        attendance_cmd = RecordAttendanceCommand(
            employee_id=current_user.id,
            zone_id=result.zone_id,
            zone_type=result.zone_type,
            now=datetime.now(tz=UTC),
        )
        attendance_log = await record_attendance_use_case.execute(attendance_cmd)
        log.info(
            "[positioning.endpoint.classify] attendance_recorded",
            employee_id=current_user.id,
            attendance_log_id=attendance_log.id,
            attendance_status=attendance_log.status.value,
        )
    except Exception:
        log.warning(
            "[positioning.endpoint.classify] attendance_record_failed",
            employee_id=current_user.id,
            zone_id=result.zone_id,
            exc_info=True,
        )

    return ClassifyResponse(
        zone_id=result.zone_id,
        zone_type=result.zone_type.value,
        confidence=float(result.confidence),
        classifier_name=result.classifier_name,
    )
