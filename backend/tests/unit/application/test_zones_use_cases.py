"""Unit-тесты use cases CRUD зон."""

from __future__ import annotations

import pytest

from app.application.zones.create_zone import CreateZoneCommand, CreateZoneUseCase
from app.application.zones.delete_zone import DeleteZoneCommand, DeleteZoneUseCase
from app.application.zones.list_zones import (
    GetZoneQuery,
    GetZoneUseCase,
    ListZonesQuery,
    ListZonesUseCase,
)
from app.application.zones.update_zone import UpdateZoneCommand, UpdateZoneUseCase
from app.domain.shared.exceptions import ConflictError, NotFoundError
from app.domain.zones.entities import ZoneType
from tests.unit.application.fakes import FakeZoneRepository

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_zone_returns_with_id() -> None:
    repo = FakeZoneRepository()
    use_case = CreateZoneUseCase(zone_repo=repo)

    zone = await use_case.execute(
        CreateZoneCommand(
            name="Рабочее место А1",
            type=ZoneType.WORKPLACE,
            description="Тест",
            display_color="#4A90E2",
        )
    )
    assert zone.id > 0
    assert zone.name == "Рабочее место А1"
    assert zone.type is ZoneType.WORKPLACE


async def test_create_zone_duplicate_name_raises_conflict() -> None:
    repo = FakeZoneRepository()
    use_case = CreateZoneUseCase(zone_repo=repo)

    await use_case.execute(
        CreateZoneCommand(name="Дубликат", type=ZoneType.WORKPLACE)
    )
    with pytest.raises(ConflictError) as exc_info:
        await use_case.execute(
            CreateZoneCommand(name="Дубликат", type=ZoneType.CORRIDOR)
        )
    assert exc_info.value.code == "zone_name_taken"


# ---------------------------------------------------------------------------
# List + Get
# ---------------------------------------------------------------------------


async def test_list_zones_with_type_filter() -> None:
    repo = FakeZoneRepository()
    create = CreateZoneUseCase(zone_repo=repo)
    await create.execute(CreateZoneCommand(name="A", type=ZoneType.WORKPLACE))
    await create.execute(CreateZoneCommand(name="B", type=ZoneType.WORKPLACE))
    await create.execute(CreateZoneCommand(name="C", type=ZoneType.CORRIDOR))

    use_case = ListZonesUseCase(zone_repo=repo)
    page = await use_case.execute(ListZonesQuery(type_filter=ZoneType.WORKPLACE))

    assert page.total == 2
    assert all(z.type is ZoneType.WORKPLACE for z in page.items)


async def test_get_zone_unknown_id_raises_not_found() -> None:
    repo = FakeZoneRepository()
    use_case = GetZoneUseCase(zone_repo=repo)

    with pytest.raises(NotFoundError) as exc_info:
        await use_case.execute(GetZoneQuery(zone_id=99999))
    assert exc_info.value.code == "zone_not_found"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


async def test_update_zone_partial() -> None:
    repo = FakeZoneRepository()
    create = CreateZoneUseCase(zone_repo=repo)
    zone = await create.execute(
        CreateZoneCommand(name="Old", type=ZoneType.WORKPLACE, description="d")
    )

    use_case = UpdateZoneUseCase(zone_repo=repo)
    updated = await use_case.execute(
        UpdateZoneCommand(zone_id=zone.id, name="New")
    )
    assert updated.name == "New"
    assert updated.type is ZoneType.WORKPLACE  # не менялся
    assert updated.description == "d"  # не менялось


async def test_update_zone_clear_optional_fields() -> None:
    repo = FakeZoneRepository()
    create = CreateZoneUseCase(zone_repo=repo)
    zone = await create.execute(
        CreateZoneCommand(
            name="Z",
            type=ZoneType.MEETING_ROOM,
            description="d",
            display_color="#FF0000",
        )
    )

    use_case = UpdateZoneUseCase(zone_repo=repo)
    updated = await use_case.execute(
        UpdateZoneCommand(
            zone_id=zone.id,
            clear_description=True,
            clear_display_color=True,
        )
    )
    assert updated.description is None
    assert updated.display_color is None


async def test_update_zone_name_collision_raises_conflict() -> None:
    repo = FakeZoneRepository()
    create = CreateZoneUseCase(zone_repo=repo)
    a = await create.execute(CreateZoneCommand(name="A", type=ZoneType.WORKPLACE))
    await create.execute(CreateZoneCommand(name="B", type=ZoneType.WORKPLACE))

    use_case = UpdateZoneUseCase(zone_repo=repo)
    with pytest.raises(ConflictError) as exc_info:
        await use_case.execute(UpdateZoneCommand(zone_id=a.id, name="B"))
    assert exc_info.value.code == "zone_name_taken"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def test_delete_zone_success() -> None:
    repo = FakeZoneRepository()
    create = CreateZoneUseCase(zone_repo=repo)
    zone = await create.execute(CreateZoneCommand(name="X", type=ZoneType.CORRIDOR))

    use_case = DeleteZoneUseCase(zone_repo=repo)
    await use_case.execute(DeleteZoneCommand(zone_id=zone.id))

    # После удаления Get → NotFound.
    get_use_case = GetZoneUseCase(zone_repo=repo)
    with pytest.raises(NotFoundError):
        await get_use_case.execute(GetZoneQuery(zone_id=zone.id))


async def test_delete_zone_in_use_raises_conflict() -> None:
    repo = FakeZoneRepository()
    create = CreateZoneUseCase(zone_repo=repo)
    zone = await create.execute(CreateZoneCommand(name="X", type=ZoneType.CORRIDOR))
    repo.mark_in_use(zone.id)  # симулируем FK RESTRICT

    use_case = DeleteZoneUseCase(zone_repo=repo)
    with pytest.raises(ConflictError) as exc_info:
        await use_case.execute(DeleteZoneCommand(zone_id=zone.id))
    assert exc_info.value.code == "zone_in_use"


async def test_delete_unknown_id_raises_not_found() -> None:
    repo = FakeZoneRepository()
    use_case = DeleteZoneUseCase(zone_repo=repo)

    with pytest.raises(NotFoundError):
        await use_case.execute(DeleteZoneCommand(zone_id=99999))
