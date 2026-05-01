"""Pydantic-схемы для healthcheck endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["ok", "fail"]
OverallStatus = Literal["ok", "degraded"]


class HealthResponse(BaseModel):
    """Ответ healthcheck endpoint.

    `status` = "ok" если все checks прошли, иначе "degraded".
    `checks` — словарь с результатом по каждой подсистеме.

    Используется для:
    - Liveness probe (Kubernetes/Docker)
    - Мониторинг (Prometheus, Grafana)
    - Проверки клиентами перед началом работы
    """

    status: OverallStatus = Field(
        ...,
        description="'ok' = все проверки прошли; 'degraded' = есть проваленные.",
    )
    version: str = Field(..., description="Версия приложения (из pyproject.toml).")
    environment: str = Field(..., description="Окружение запуска (development/staging/production).")
    checks: dict[str, CheckStatus] = Field(
        default_factory=dict,
        description="Результаты по подсистемам: app, database, ml-model, ...",
    )
