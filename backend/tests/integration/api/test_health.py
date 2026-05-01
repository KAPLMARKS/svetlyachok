"""Интеграционные тесты healthcheck endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.presentation.middleware.correlation_id import CORRELATION_ID_HEADER


pytestmark = pytest.mark.integration


async def test_health_returns_200_ok(client: AsyncClient) -> None:
    """GET /api/v1/health возвращает 200 со status='ok'."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "development"
    assert "checks" in body
    assert body["checks"]["app"] == "ok"
    assert body["checks"]["database"] == "ok"  # сейчас заглушка


async def test_health_response_includes_correlation_id_header(
    client: AsyncClient,
) -> None:
    """Сервер автоматически добавляет X-Correlation-ID в ответ."""
    response = await client.get("/api/v1/health")

    assert CORRELATION_ID_HEADER in response.headers
    correlation_id = response.headers[CORRELATION_ID_HEADER]
    assert correlation_id  # не пустой
    assert len(correlation_id) >= 16  # UUID hex или клиентский id


async def test_health_echoes_provided_correlation_id(client: AsyncClient) -> None:
    """Если клиент передал X-Correlation-ID, он отражается в ответе."""
    custom_id = "test-correlation-12345"
    response = await client.get(
        "/api/v1/health",
        headers={CORRELATION_ID_HEADER: custom_id},
    )

    assert response.status_code == 200
    assert response.headers[CORRELATION_ID_HEADER] == custom_id


async def test_health_response_has_version_field(client: AsyncClient) -> None:
    """В ответе должно быть поле version (строка)."""
    response = await client.get("/api/v1/health")
    body = response.json()

    assert "version" in body
    assert isinstance(body["version"], str)
    assert body["version"]  # не пустая
