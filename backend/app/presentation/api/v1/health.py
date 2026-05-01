"""Healthcheck endpoint.

GET /api/v1/health
- 200 OK с status="ok" если все подсистемы здоровы
- 200 OK с status="degraded" если хотя бы одна failed (детали в checks)

Возвращает 200 даже при degraded — балансировщик не должен трактовать
healthcheck как auth/роутинг-эндпоинт. Если позже потребуется отдельный
liveness vs readiness — добавим `/api/v1/ready` с 503 на degraded.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Literal

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.infrastructure.db.healthcheck import check_database
from app.presentation.dependencies import get_db_sessionmaker_dep
from app.presentation.schemas.health import HealthResponse

log = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Healthcheck",
    description="Возвращает состояние приложения и его подсистем.",
)
async def health_check(
    settings: Settings = Depends(get_settings),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_db_sessionmaker_dep),
) -> HealthResponse:
    log.debug("[health.check] start")

    checks: dict[str, Literal["ok", "fail"]] = {
        "app": "ok",
        "database": await check_database(session_factory),
    }

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    if overall == "degraded":
        failed = [k for k, v in checks.items() if v == "fail"]
        log.warning("[health.check] degraded", failed_checks=failed)
    else:
        log.debug("[health.check] done", status=overall, checks=checks)

    return HealthResponse(
        status=overall,
        version=_app_version(),
        environment=settings.environment,
        checks=checks,
    )


def _app_version() -> str:
    """Возвращает версию пакета из pyproject.toml.

    Если пакет не установлен (например, запуск из исходников без
    `pip install -e`), возвращает '0.0.0-dev' как fallback.
    """
    try:
        return version("svetlyachok-backend")
    except PackageNotFoundError:
        return "0.0.0-dev"
