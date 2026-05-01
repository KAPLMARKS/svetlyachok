"""Unit-тесты JwtProvider — encode/decode round-trip и негативные кейсы."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest

from app.core.config import get_settings
from app.domain.shared.exceptions import UnauthorizedError
from app.infrastructure.auth.jwt_provider import JwtProvider

pytestmark = pytest.mark.unit


@pytest.fixture
def provider() -> JwtProvider:
    """JwtProvider с тестовыми настройками."""
    return JwtProvider(get_settings())


def test_encode_decode_access_round_trip(provider: JwtProvider) -> None:
    token, exp = provider.encode_access_token(subject="42", role="admin")
    assert isinstance(token, str)
    assert exp > datetime.now(tz=UTC)

    claims = provider.decode(token, expected_type="access")
    assert claims.sub == "42"
    assert claims.role == "admin"
    assert claims.type == "access"
    assert claims.jti  # uuid4 hex, непустой


def test_encode_decode_refresh_round_trip(provider: JwtProvider) -> None:
    token, _ = provider.encode_refresh_token(subject="42")
    claims = provider.decode(token, expected_type="refresh")
    assert claims.sub == "42"
    assert claims.role is None
    assert claims.type == "refresh"


def test_decode_with_wrong_type_raises_unauthorized(provider: JwtProvider) -> None:
    """access токен нельзя выдать за refresh."""
    access, _ = provider.encode_access_token(subject="1", role="employee")
    with pytest.raises(UnauthorizedError) as exc_info:
        provider.decode(access, expected_type="refresh")
    assert exc_info.value.code == "wrong_token_type"


def test_decode_garbage_raises_unauthorized(provider: JwtProvider) -> None:
    with pytest.raises(UnauthorizedError) as exc_info:
        provider.decode("not.a.jwt", expected_type="access")
    assert exc_info.value.code == "invalid_token"


def test_decode_with_different_secret_raises_unauthorized(
    provider: JwtProvider,
) -> None:
    """Токен, подписанный чужим секретом, не должен пройти."""
    payload = {
        "sub": "1",
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    foreign = pyjwt.encode(payload, "different_secret_at_least_32_chars_x", algorithm="HS256")
    with pytest.raises(UnauthorizedError) as exc_info:
        provider.decode(foreign, expected_type="access")
    assert exc_info.value.code == "invalid_token"


def test_decode_expired_token_raises_unauthorized(provider: JwtProvider) -> None:
    """Истекший токен → expired_token."""
    # Конструируем заведомо истёкший токен с тем же секретом, что и provider.
    settings = get_settings()
    expired_payload = {
        "sub": "1",
        "type": "access",
        "iat": int((datetime.now(tz=UTC) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(tz=UTC) - timedelta(hours=1)).timestamp()),
    }
    expired_token = pyjwt.encode(
        expired_payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        provider.decode(expired_token, expected_type="access")
    assert exc_info.value.code == "expired_token"


def test_decode_token_without_sub_raises_unauthorized(provider: JwtProvider) -> None:
    """Токен без sub — нелегитимный."""
    settings = get_settings()
    payload = {
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    no_sub = pyjwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        provider.decode(no_sub, expected_type="access")
    assert exc_info.value.code == "invalid_token"
