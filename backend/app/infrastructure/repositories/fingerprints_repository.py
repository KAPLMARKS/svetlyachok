"""SQLAlchemy-реализация FingerprintRepository.

Маппит ORM `FingerprintORM` ↔ domain `Fingerprint`. JSONB-поле
`rssi_vector` сериализуется через `RSSIVector.to_dict()` при записи и
десериализуется обратно при чтении.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.radiomap.entities import Fingerprint
from app.domain.radiomap.repositories import FingerprintRepository
from app.domain.radiomap.value_objects import RSSIVector
from app.domain.shared.exceptions import ValidationError
from app.infrastructure.db.orm.radiomap import Fingerprint as FingerprintORM

log = get_logger(__name__)


class SqlAlchemyFingerprintRepository(FingerprintRepository):
    """Async-репозиторий радиоотпечатков на SQLAlchemy 2.x."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, fingerprint: Fingerprint) -> Fingerprint:
        log.debug(
            "[fingerprints.repo.add] start",
            employee_id=fingerprint.employee_id,
            zone_id=fingerprint.zone_id,
            is_calibration=fingerprint.is_calibration,
            ap_count=len(fingerprint.rssi_vector),
        )
        orm = FingerprintORM(
            employee_id=fingerprint.employee_id,
            zone_id=fingerprint.zone_id,
            is_calibration=fingerprint.is_calibration,
            captured_at=fingerprint.captured_at,
            device_id=fingerprint.device_id,
            rssi_vector=fingerprint.rssi_vector.to_dict(),
            sample_count=fingerprint.sample_count,
        )
        self._session.add(orm)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            # Defense-in-depth: доменный инвариант ловится в Fingerprint.__post_init__,
            # но при ручных вставках через SQL CHECK calibration_requires_zone
            # тоже может сработать. Конвертируем в ValidationError.
            log.warning(
                "[fingerprints.repo.add] integrity_error",
                exc_type=type(exc).__name__,
            )
            raise ValidationError(
                code="fingerprint_integrity_violation",
                message="Не удалось сохранить отпечаток (нарушение инварианта схемы БД)",
            ) from exc

        await self._session.refresh(orm)
        result = self._to_domain(orm)
        log.info(
            "[fingerprints.repo.add] done",
            fingerprint_id=result.id,
            is_calibration=result.is_calibration,
        )
        return result

    async def get_by_id(self, fingerprint_id: int) -> Fingerprint | None:
        log.debug("[fingerprints.repo.get_by_id] start", id=fingerprint_id)
        stmt = select(FingerprintORM).where(FingerprintORM.id == fingerprint_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        result = self._to_domain(orm) if orm is not None else None
        log.debug(
            "[fingerprints.repo.get_by_id] done",
            id=fingerprint_id,
            found=result is not None,
        )
        return result

    async def list(
        self,
        *,
        employee_id: int | None = None,
        zone_id: int | None = None,
        is_calibration: bool | None = None,
        captured_from: datetime | None = None,
        captured_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Fingerprint]:
        log.debug(
            "[fingerprints.repo.list] start",
            employee_id=employee_id,
            zone_id=zone_id,
            is_calibration=is_calibration,
            limit=limit,
            offset=offset,
        )
        stmt = select(FingerprintORM).order_by(FingerprintORM.captured_at.desc())
        stmt = self._apply_filters(
            stmt,
            employee_id=employee_id,
            zone_id=zone_id,
            is_calibration=is_calibration,
            captured_from=captured_from,
            captured_to=captured_to,
        )
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        result = [self._to_domain(orm) for orm in rows]
        log.debug("[fingerprints.repo.list] done", returned=len(result))
        return result

    async def count(
        self,
        *,
        employee_id: int | None = None,
        zone_id: int | None = None,
        is_calibration: bool | None = None,
        captured_from: datetime | None = None,
        captured_to: datetime | None = None,
    ) -> int:
        log.debug("[fingerprints.repo.count] start")
        stmt = select(func.count()).select_from(FingerprintORM)
        stmt = self._apply_filters(
            stmt,
            employee_id=employee_id,
            zone_id=zone_id,
            is_calibration=is_calibration,
            captured_from=captured_from,
            captured_to=captured_to,
        )
        total = (await self._session.execute(stmt)).scalar_one()
        log.debug("[fingerprints.repo.count] done", total=total)
        return int(total)

    async def delete_by_id(self, fingerprint_id: int) -> bool:
        log.debug("[fingerprints.repo.delete_by_id] start", id=fingerprint_id)
        stmt = select(FingerprintORM).where(FingerprintORM.id == fingerprint_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            log.debug("[fingerprints.repo.delete_by_id] not_found", id=fingerprint_id)
            return False
        await self._session.delete(orm)
        await self._session.flush()
        log.info("[fingerprints.repo.delete_by_id] done", fingerprint_id=fingerprint_id)
        return True

    async def list_calibrated_for_zone(self, zone_id: int) -> list[Fingerprint]:
        """Все калибровочные отпечатки конкретной зоны (для ML).

        Использует partial-индекс `ix_fingerprints_zone_calibration` —
        запрос `WHERE zone_id = ? AND is_calibration = true` отрабатывает
        быстро даже на больших таблицах.
        """
        log.debug("[fingerprints.repo.list_calibrated_for_zone] start", zone_id=zone_id)
        stmt = (
            select(FingerprintORM)
            .where(FingerprintORM.zone_id == zone_id)
            .where(FingerprintORM.is_calibration.is_(True))
            .order_by(FingerprintORM.captured_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        result = [self._to_domain(orm) for orm in rows]
        log.debug(
            "[fingerprints.repo.list_calibrated_for_zone] done",
            zone_id=zone_id,
            returned=len(result),
        )
        return result

    async def list_calibrated_all(self) -> list[Fingerprint]:
        """Все калибровочные отпечатки во всех зонах (для ML)."""
        log.debug("[fingerprints.repo.list_calibrated_all] start")
        stmt = (
            select(FingerprintORM)
            .where(FingerprintORM.is_calibration.is_(True))
            .where(FingerprintORM.zone_id.is_not(None))
            .order_by(FingerprintORM.captured_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        result = [self._to_domain(orm) for orm in rows]
        log.debug(
            "[fingerprints.repo.list_calibrated_all] done", returned=len(result)
        )
        return result

    @staticmethod
    def _apply_filters(
        stmt,
        *,
        employee_id: int | None,
        zone_id: int | None,
        is_calibration: bool | None,
        captured_from: datetime | None,
        captured_to: datetime | None,
    ):
        if employee_id is not None:
            stmt = stmt.where(FingerprintORM.employee_id == employee_id)
        if zone_id is not None:
            stmt = stmt.where(FingerprintORM.zone_id == zone_id)
        if is_calibration is not None:
            stmt = stmt.where(FingerprintORM.is_calibration.is_(is_calibration))
        if captured_from is not None:
            stmt = stmt.where(FingerprintORM.captured_at >= captured_from)
        if captured_to is not None:
            stmt = stmt.where(FingerprintORM.captured_at <= captured_to)
        return stmt

    @staticmethod
    def _to_domain(orm: FingerprintORM) -> Fingerprint:
        """Маппер ORM → domain. JSONB → RSSIVector."""
        return Fingerprint(
            id=orm.id,
            employee_id=orm.employee_id,
            zone_id=orm.zone_id,
            is_calibration=orm.is_calibration,
            captured_at=orm.captured_at,
            device_id=orm.device_id,
            rssi_vector=RSSIVector(orm.rssi_vector),
            sample_count=orm.sample_count,
        )
