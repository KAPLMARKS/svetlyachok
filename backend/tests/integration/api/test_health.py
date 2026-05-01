"""Интеграционные тесты healthcheck endpoint."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.presentation.dependencies import get_db_sessionmaker_dep
from app.presentation.middleware.correlation_id import CORRELATION_ID_HEADER

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Тесты, не требующие настоящей БД — для них мокаем session_factory.
# ---------------------------------------------------------------------------


class _FakeSession:
    """Минимальный стуб AsyncSession для healthcheck."""

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        if self._fail:
            raise ConnectionRefusedError("simulated DB outage")


def _make_session_factory(*, fail: bool):
    def factory() -> _FakeSession:
        return _FakeSession(fail=fail)

    return factory


@pytest.fixture
def app_with_fake_db_ok(app: FastAPI) -> FastAPI:
    """FastAPI с подменой session_factory на стуб (имитирует здоровую БД)."""
    app.dependency_overrides[get_db_sessionmaker_dep] = lambda: _make_session_factory(fail=False)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def app_with_fake_db_fail(app: FastAPI) -> FastAPI:
    """FastAPI с подменой session_factory на стуб (имитирует упавшую БД)."""
    app.dependency_overrides[get_db_sessionmaker_dep] = lambda: _make_session_factory(fail=True)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client_ok(app_with_fake_db_ok: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app_with_fake_db_ok)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client_fail(app_with_fake_db_fail: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app_with_fake_db_fail)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Базовые тесты — БД отвечает успешно
# ---------------------------------------------------------------------------


async def test_health_returns_200_ok_when_db_healthy(
    client_ok: AsyncClient,
) -> None:
    """GET /api/v1/health возвращает 200 со status='ok' при здоровой БД."""
    response = await client_ok.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "development"
    assert body["checks"]["app"] == "ok"
    assert body["checks"]["database"] == "ok"


async def test_health_response_includes_correlation_id_header(
    client_ok: AsyncClient,
) -> None:
    """Сервер автоматически добавляет X-Correlation-ID в ответ."""
    response = await client_ok.get("/api/v1/health")

    assert CORRELATION_ID_HEADER in response.headers
    correlation_id = response.headers[CORRELATION_ID_HEADER]
    assert correlation_id
    assert len(correlation_id) >= 16


async def test_health_echoes_provided_correlation_id(client_ok: AsyncClient) -> None:
    """Если клиент передал X-Correlation-ID, он отражается в ответе."""
    custom_id = "test-correlation-12345"
    response = await client_ok.get(
        "/api/v1/health",
        headers={CORRELATION_ID_HEADER: custom_id},
    )

    assert response.status_code == 200
    assert response.headers[CORRELATION_ID_HEADER] == custom_id


async def test_health_response_has_version_field(client_ok: AsyncClient) -> None:
    """В ответе должно быть поле version (строка)."""
    response = await client_ok.get("/api/v1/health")
    body = response.json()

    assert "version" in body
    assert isinstance(body["version"], str)
    assert body["version"]


# ---------------------------------------------------------------------------
# БД недоступна — degraded, но 200 OK
# ---------------------------------------------------------------------------


async def test_health_degraded_when_db_fails(client_fail: AsyncClient) -> None:
    """При недоступной БД — checks.database='fail', status='degraded',
    response code остаётся 200 (см. policy в health.py)."""
    response = await client_fail.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["app"] == "ok"
    assert body["checks"]["database"] == "fail"
