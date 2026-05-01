"""SQLAlchemy-реализация ZoneRepository."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.shared.exceptions import ConflictError, NotFoundError
from app.domain.zones.entities import Zone, ZoneType
from app.domain.zones.repositories import ZoneRepository
from app.infrastructure.db.orm.zones import Zone as ZoneORM
from app.infrastructure.db.orm.zones import ZoneType as OrmZoneType

log = get_logger(__name__)


class SqlAlchemyZoneRepository(ZoneRepository):
    """Async-репозиторий зон на SQLAlchemy 2.x."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, zone_id: int) -> Zone | None:
        log.debug("[zones.repo.get_by_id] start", id=zone_id)
        stmt = select(ZoneORM).where(ZoneORM.id == zone_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        result = self._to_domain(orm) if orm is not None else None
        log.debug("[zones.repo.get_by_id] done", id=zone_id, found=result is not None)
        return result

    async def get_by_name(self, name: str) -> Zone | None:
        log.debug("[zones.repo.get_by_name] start", name=name)
        stmt = select(ZoneORM).where(ZoneORM.name == name)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        result = self._to_domain(orm) if orm is not None else None
        log.debug(
            "[zones.repo.get_by_name] done", name=name, found=result is not None
        )
        return result

    async def list(
        self,
        *,
        type_filter: ZoneType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Zone]:
        log.debug(
            "[zones.repo.list] start",
            type_filter=type_filter.value if type_filter else None,
            limit=limit,
            offset=offset,
        )
        stmt = select(ZoneORM).order_by(ZoneORM.id.asc())
        if type_filter is not None:
            stmt = stmt.where(ZoneORM.type == OrmZoneType(type_filter.value))
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        result = [self._to_domain(orm) for orm in rows]
        log.debug("[zones.repo.list] done", returned=len(result))
        return result

    async def count(self, *, type_filter: ZoneType | None = None) -> int:
        log.debug(
            "[zones.repo.count] start",
            type_filter=type_filter.value if type_filter else None,
        )
        stmt = select(func.count()).select_from(ZoneORM)
        if type_filter is not None:
            stmt = stmt.where(ZoneORM.type == OrmZoneType(type_filter.value))
        total = (await self._session.execute(stmt)).scalar_one()
        log.debug("[zones.repo.count] done", total=total)
        return int(total)

    async def add(self, zone: Zone) -> Zone:
        log.debug("[zones.repo.add] start", name=zone.name)
        orm = ZoneORM(
            name=zone.name,
            type=OrmZoneType(zone.type.value),
            description=zone.description,
            display_color=zone.display_color,
        )
        self._session.add(orm)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            log.warning(
                "[zones.repo.add] conflict",
                name=zone.name,
                exc_type=type(exc).__name__,
            )
            raise ConflictError(
                code="zone_name_taken",
                message=f"Зона с именем {zone.name!r} уже существует",
            ) from exc

        await self._session.refresh(orm)
        result = self._to_domain(orm)
        log.info("[zones.repo.add] done", zone_id=result.id, name=result.name)
        return result

    async def update(self, zone: Zone) -> Zone:
        log.debug("[zones.repo.update] start", id=zone.id)
        stmt = select(ZoneORM).where(ZoneORM.id == zone.id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            log.warning("[zones.repo.update] not_found", id=zone.id)
            raise NotFoundError(
                code="zone_not_found",
                message=f"Зона с id={zone.id} не найдена",
            )

        orm.name = zone.name
        orm.type = OrmZoneType(zone.type.value)
        orm.description = zone.description
        orm.display_color = zone.display_color

        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            log.warning(
                "[zones.repo.update] conflict",
                id=zone.id,
                exc_type=type(exc).__name__,
            )
            raise ConflictError(
                code="zone_name_taken",
                message=f"Зона с именем {zone.name!r} уже существует",
            ) from exc

        await self._session.refresh(orm)
        result = self._to_domain(orm)
        log.info("[zones.repo.update] done", zone_id=result.id)
        return result

    async def delete_by_id(self, zone_id: int) -> bool:
        """Удаляет зону. False если не найдена.

        Если зона связана с attendance_logs (FK ondelete=RESTRICT),
        Postgres поднимает IntegrityError → ConflictError(zone_in_use).
        """
        log.debug("[zones.repo.delete_by_id] start", id=zone_id)
        stmt = select(ZoneORM).where(ZoneORM.id == zone_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            log.debug("[zones.repo.delete_by_id] not_found", id=zone_id)
            return False

        await self._session.delete(orm)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            log.warning(
                "[zones.repo.delete_by_id] conflict",
                id=zone_id,
                exc_type=type(exc).__name__,
            )
            raise ConflictError(
                code="zone_in_use",
                message=(
                    f"Зону с id={zone_id} нельзя удалить — "
                    "на неё ссылаются записи учёта посещаемости"
                ),
                details={"reason": "attendance_logs_exist"},
            ) from exc

        log.info("[zones.repo.delete_by_id] done", zone_id=zone_id)
        return True

    @staticmethod
    def _to_domain(orm: ZoneORM) -> Zone:
        return Zone(
            id=orm.id,
            name=orm.name,
            type=ZoneType(orm.type.value),
            description=orm.description,
            display_color=orm.display_color,
        )
