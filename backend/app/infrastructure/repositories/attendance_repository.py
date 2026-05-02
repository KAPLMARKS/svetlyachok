"""SQLAlchemy-реализация AttendanceRepository.

Маппит ORM `AttendanceLog` (infrastructure) ↔ domain `AttendanceLog`.
Использует partial-индекс `ix_attendance_logs_open_sessions` для быстрого
поиска открытых сессий сотрудника.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.attendance.entities import AttendanceLog
from app.domain.attendance.repositories import AttendanceRepository
from app.domain.attendance.value_objects import AttendanceStatus
from app.domain.shared.exceptions import NotFoundError
from app.infrastructure.db.orm.attendance import AttendanceLog as AttendanceLogORM
from app.infrastructure.db.orm.attendance import (
    AttendanceStatus as AttendanceStatusORM,
)

log = get_logger(__name__)


class SqlAlchemyAttendanceRepository(AttendanceRepository):
    """Async-репозиторий записей посещаемости на SQLAlchemy 2.x."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, log_entry: AttendanceLog) -> AttendanceLog:
        log.debug(
            "[attendance.repo.add] start",
            employee_id=log_entry.employee_id,
            zone_id=log_entry.zone_id,
            status=log_entry.status.value,
        )
        orm = AttendanceLogORM(
            employee_id=log_entry.employee_id,
            zone_id=log_entry.zone_id,
            started_at=log_entry.started_at,
            ended_at=log_entry.ended_at,
            last_seen_at=log_entry.last_seen_at,
            duration_seconds=log_entry.duration_seconds,
            status=AttendanceStatusORM(log_entry.status.value),
        )
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        result = self._to_domain(orm)
        log.info(
            "[attendance.repo.add] done",
            attendance_log_id=result.id,
            employee_id=result.employee_id,
            zone_id=result.zone_id,
            is_open=result.is_open,
        )
        return result

    async def update(self, log_entry: AttendanceLog) -> AttendanceLog:
        log.debug(
            "[attendance.repo.update] start",
            attendance_log_id=log_entry.id,
            is_open=log_entry.is_open,
        )
        stmt = select(AttendanceLogORM).where(AttendanceLogORM.id == log_entry.id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            log.warning(
                "[attendance.repo.update] not_found",
                attendance_log_id=log_entry.id,
            )
            raise NotFoundError(
                code="attendance_log_not_found",
                message=f"AttendanceLog id={log_entry.id} не найден",
            )
        orm.zone_id = log_entry.zone_id
        orm.started_at = log_entry.started_at
        orm.ended_at = log_entry.ended_at
        orm.last_seen_at = log_entry.last_seen_at
        orm.duration_seconds = log_entry.duration_seconds
        orm.status = AttendanceStatusORM(log_entry.status.value)
        await self._session.flush()
        await self._session.refresh(orm)
        result = self._to_domain(orm)
        log.info(
            "[attendance.repo.update] done",
            attendance_log_id=result.id,
            is_open=result.is_open,
            duration_seconds=result.duration_seconds,
        )
        return result

    async def get_by_id(self, log_id: int) -> AttendanceLog | None:
        log.debug("[attendance.repo.get_by_id] start", id=log_id)
        stmt = select(AttendanceLogORM).where(AttendanceLogORM.id == log_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        result = self._to_domain(orm) if orm is not None else None
        log.debug(
            "[attendance.repo.get_by_id] done", id=log_id, found=result is not None
        )
        return result

    async def get_open_session_for_employee(
        self, employee_id: int
    ) -> AttendanceLog | None:
        log.debug(
            "[attendance.repo.get_open_session_for_employee] start",
            employee_id=employee_id,
        )
        stmt = (
            select(AttendanceLogORM)
            .where(AttendanceLogORM.employee_id == employee_id)
            .where(AttendanceLogORM.ended_at.is_(None))
            .order_by(AttendanceLogORM.started_at.desc())
            .limit(1)
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        result = self._to_domain(orm) if orm is not None else None
        log.debug(
            "[attendance.repo.get_open_session_for_employee] done",
            employee_id=employee_id,
            found=result is not None,
        )
        return result

    async def list(
        self,
        *,
        employee_id: int | None = None,
        zone_id: int | None = None,
        status: AttendanceStatus | None = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AttendanceLog]:
        log.debug(
            "[attendance.repo.list] start",
            employee_id=employee_id,
            zone_id=zone_id,
            status=status.value if status else None,
            limit=limit,
            offset=offset,
        )
        stmt = select(AttendanceLogORM).order_by(AttendanceLogORM.started_at.desc())
        stmt = self._apply_filters(
            stmt,
            employee_id=employee_id,
            zone_id=zone_id,
            status=status,
            started_from=started_from,
            started_to=started_to,
        )
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        result = [self._to_domain(orm) for orm in rows]
        log.debug("[attendance.repo.list] done", returned=len(result))
        return result

    async def count(
        self,
        *,
        employee_id: int | None = None,
        zone_id: int | None = None,
        status: AttendanceStatus | None = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
    ) -> int:
        log.debug("[attendance.repo.count] start")
        stmt = select(func.count()).select_from(AttendanceLogORM)
        stmt = self._apply_filters(
            stmt,
            employee_id=employee_id,
            zone_id=zone_id,
            status=status,
            started_from=started_from,
            started_to=started_to,
        )
        total = (await self._session.execute(stmt)).scalar_one()
        log.debug("[attendance.repo.count] done", total=total)
        return int(total)

    @staticmethod
    def _apply_filters(
        stmt: Select[Any],
        *,
        employee_id: int | None,
        zone_id: int | None,
        status: AttendanceStatus | None,
        started_from: datetime | None,
        started_to: datetime | None,
    ) -> Select[Any]:
        if employee_id is not None:
            stmt = stmt.where(AttendanceLogORM.employee_id == employee_id)
        if zone_id is not None:
            stmt = stmt.where(AttendanceLogORM.zone_id == zone_id)
        if status is not None:
            stmt = stmt.where(
                AttendanceLogORM.status == AttendanceStatusORM(status.value)
            )
        if started_from is not None:
            stmt = stmt.where(AttendanceLogORM.started_at >= started_from)
        if started_to is not None:
            stmt = stmt.where(AttendanceLogORM.started_at <= started_to)
        return stmt

    @staticmethod
    def _to_domain(orm: AttendanceLogORM) -> AttendanceLog:
        """Маппер ORM → domain. ORM-enum → domain-enum по value."""
        return AttendanceLog(
            id=orm.id,
            employee_id=orm.employee_id,
            zone_id=orm.zone_id,
            started_at=orm.started_at,
            ended_at=orm.ended_at,
            last_seen_at=orm.last_seen_at,
            duration_seconds=orm.duration_seconds,
            status=AttendanceStatus(orm.status.value),
        )
