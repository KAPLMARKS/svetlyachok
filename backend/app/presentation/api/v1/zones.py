"""Эндпоинты CRUD зон.

Матрица доступа:

| Эндпоинт            | Admin | Authenticated | Anonymous |
|---------------------|-------|---------------|-----------|
| POST   /zones       | OK    | 403           | 401       |
| GET    /zones       | OK    | OK            | 401       |
| GET    /zones/{id}  | OK    | OK            | 401       |
| PATCH  /zones/{id}  | OK    | 403           | 401       |
| DELETE /zones/{id}  | OK    | 403           | 401       |

GET-операции открыты любому авторизованному, т.к. mobile/web-клиентам
нужен список зон для UI (выбор зоны при ручной калибровке, отображение
карты).

DELETE при наличии связанных attendance_logs возвращает 409
`zone_in_use` — реальное удаление возможно только когда нет истории.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.application.zones.create_zone import (
    CreateZoneCommand,
    CreateZoneUseCase,
)
from app.application.zones.delete_zone import (
    DeleteZoneCommand,
    DeleteZoneUseCase,
)
from app.application.zones.list_zones import (
    GetZoneQuery,
    GetZoneUseCase,
    ListZonesQuery,
    ListZonesUseCase,
)
from app.application.zones.update_zone import (
    UpdateZoneCommand,
    UpdateZoneUseCase,
)
from app.core.logging import get_logger
from app.domain.employees.entities import Employee, Role
from app.domain.zones.entities import Zone, ZoneType
from app.presentation.dependencies import (
    get_create_zone_use_case,
    get_current_user,
    get_delete_zone_use_case,
    get_list_zones_use_case,
    get_update_zone_use_case,
    get_zone_use_case,
    require_role,
)
from app.presentation.schemas.zones import (
    ZoneCreateRequest,
    ZoneResponse,
    ZonesPageResponse,
    ZoneUpdateRequest,
)

log = get_logger(__name__)

router = APIRouter(prefix="/zones", tags=["zones"])


def _to_response(zone: Zone) -> ZoneResponse:
    return ZoneResponse(
        id=zone.id,
        name=zone.name,
        type=zone.type.value,
        description=zone.description,
        display_color=zone.display_color,
    )


@router.post(
    "",
    response_model=ZoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать зону (admin)",
)
async def create_zone(
    payload: ZoneCreateRequest,
    _: Employee = Depends(require_role(Role.ADMIN)),
    use_case: CreateZoneUseCase = Depends(get_create_zone_use_case),
) -> ZoneResponse:
    log.debug("[zones.endpoint.create] start", name=payload.name)

    cmd = CreateZoneCommand(
        name=payload.name,
        type=payload.type,
        description=payload.description,
        display_color=payload.display_color,
    )
    zone = await use_case.execute(cmd)
    return _to_response(zone)


@router.get(
    "",
    response_model=ZonesPageResponse,
    summary="Список зон (любой авторизованный)",
)
async def list_zones(
    type_filter: ZoneType | None = Query(
        default=None,
        alias="type",
        description="Фильтр по типу зоны",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: Employee = Depends(get_current_user),
    use_case: ListZonesUseCase = Depends(get_list_zones_use_case),
) -> ZonesPageResponse:
    log.debug(
        "[zones.endpoint.list] start",
        type_filter=type_filter.value if type_filter else None,
        limit=limit,
        offset=offset,
    )

    page = await use_case.execute(
        ListZonesQuery(type_filter=type_filter, limit=limit, offset=offset)
    )
    return ZonesPageResponse(
        items=[_to_response(z) for z in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{zone_id}",
    response_model=ZoneResponse,
    summary="Получить зону по id (любой авторизованный)",
)
async def get_zone(
    zone_id: int,
    _: Employee = Depends(get_current_user),
    use_case: GetZoneUseCase = Depends(get_zone_use_case),
) -> ZoneResponse:
    log.debug("[zones.endpoint.get] start", zone_id=zone_id)
    zone = await use_case.execute(GetZoneQuery(zone_id=zone_id))
    return _to_response(zone)


@router.patch(
    "/{zone_id}",
    response_model=ZoneResponse,
    summary="Обновить зону (admin)",
)
async def update_zone(
    zone_id: int,
    payload: ZoneUpdateRequest,
    _: Employee = Depends(require_role(Role.ADMIN)),
    use_case: UpdateZoneUseCase = Depends(get_update_zone_use_case),
) -> ZoneResponse:
    log.debug("[zones.endpoint.update] start", zone_id=zone_id)
    cmd = UpdateZoneCommand(
        zone_id=zone_id,
        name=payload.name,
        type=payload.type,
        description=payload.description,
        display_color=payload.display_color,
        clear_description=payload.clear_description,
        clear_display_color=payload.clear_display_color,
    )
    zone = await use_case.execute(cmd)
    return _to_response(zone)


@router.delete(
    "/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить зону (admin). 409 если есть связанные attendance_logs.",
)
async def delete_zone(
    zone_id: int,
    _: Employee = Depends(require_role(Role.ADMIN)),
    use_case: DeleteZoneUseCase = Depends(get_delete_zone_use_case),
) -> Response:
    log.debug("[zones.endpoint.delete] start", zone_id=zone_id)
    await use_case.execute(DeleteZoneCommand(zone_id=zone_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
