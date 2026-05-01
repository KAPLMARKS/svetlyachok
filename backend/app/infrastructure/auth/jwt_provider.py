"""JWT provider на PyJWT (HS256).

Два типа токенов:

- **access** — короткоживущий (30 мин по умолчанию), несёт role в payload,
  используется для авторизации запросов.
- **refresh** — долгоживущий (7 дней), без role, используется только
  для обмена на новую пару токенов.

Поле `type` в payload защищает от подмены: refresh-токен нельзя выдать
за access (и наоборот) — `decode(expected_type=...)` это проверит.

Поле `jti` (JWT ID, uuid4) заложено для будущего blacklist'а отозванных
токенов (см. открытые вопросы плана).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import jwt
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    InvalidSignatureError,
    InvalidTokenError,
)

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.shared.exceptions import UnauthorizedError

log = get_logger(__name__)


TokenType = Literal["access", "refresh"]


@dataclass(frozen=True)
class JwtClaims:
    """Расшифрованные claims JWT.

    Frozen для безопасности: после decode никто не должен модифицировать
    sub/role; это часть авторизационного контекста.
    """

    sub: str
    role: str | None
    type: TokenType
    iat: datetime
    exp: datetime
    jti: str


class JwtProvider:
    """Кодирует/декодирует JWT по HS256 с секретом из Settings.

    Stateless — потокобезопасен. Создаётся один раз через DI.
    """

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret.get_secret_value()
        self._algorithm = settings.jwt_algorithm
        self._access_ttl = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        self._refresh_ttl = timedelta(days=settings.jwt_refresh_token_expire_days)

    def encode_access_token(self, subject: str, role: str) -> tuple[str, datetime]:
        """Возвращает (token, expires_at).

        expires_at нужен наружу, чтобы LoginUseCase отдал клиенту
        `expires_in = (exp - now).seconds` для proactive-refresh.
        """
        return self._encode(subject=subject, role=role, token_type="access", ttl=self._access_ttl)  # noqa: S106

    def encode_refresh_token(self, subject: str) -> tuple[str, datetime]:
        """Refresh без role — он не используется для авторизации запросов.

        Это упрощает rotation в будущем: при ротации мы не зависим от
        старой role (которая могла измениться).
        """
        return self._encode(
            subject=subject,
            role=None,
            token_type="refresh",  # noqa: S106
            ttl=self._refresh_ttl,
        )

    def decode(self, token: str, expected_type: TokenType) -> JwtClaims:
        """Возвращает JwtClaims или поднимает UnauthorizedError.

        Конкретные коды ошибок (для логирования и диагностики, в response
        кладём общее `invalid_token` через exception handler):
          - expired_token — exp истёк
          - invalid_signature — кто-то подписал чужим секретом
          - wrong_token_type — access вместо refresh или наоборот
          - invalid_token — мусор, повреждённый payload, неподдерживаемый алгоритм
        """
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
            )
        except ExpiredSignatureError as exc:
            log.warning(
                "[auth.jwt.decode] fail",
                reason="expired",
                exc_type=type(exc).__name__,
            )
            raise UnauthorizedError(
                code="expired_token",
                message="Срок действия токена истёк",
            ) from exc
        except InvalidSignatureError as exc:
            log.warning(
                "[auth.jwt.decode] fail",
                reason="invalid_signature",
                exc_type=type(exc).__name__,
            )
            raise UnauthorizedError(
                code="invalid_token",
                message="Недействительный токен",
            ) from exc
        except (DecodeError, InvalidTokenError) as exc:
            log.warning(
                "[auth.jwt.decode] fail",
                reason="malformed",
                exc_type=type(exc).__name__,
            )
            raise UnauthorizedError(
                code="invalid_token",
                message="Недействительный токен",
            ) from exc

        actual_type = payload.get("type")
        if actual_type != expected_type:
            log.warning(
                "[auth.jwt.decode] fail",
                reason="wrong_type",
                expected=expected_type,
                actual=actual_type,
            )
            raise UnauthorizedError(
                code="wrong_token_type",
                message="Неверный тип токена",
            )

        sub = payload.get("sub")
        if not isinstance(sub, str):
            log.warning(
                "[auth.jwt.decode] fail",
                reason="missing_sub",
                sub_type=type(sub).__name__,
            )
            raise UnauthorizedError(
                code="invalid_token",
                message="Недействительный токен",
            )

        claims = JwtClaims(
            sub=sub,
            role=payload.get("role"),
            type=actual_type,
            iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            jti=payload.get("jti", ""),
        )
        log.debug(
            "[auth.jwt.decode] ok",
            type=claims.type,
            subject=claims.sub,
        )
        return claims

    def _encode(
        self,
        *,
        subject: str,
        role: str | None,
        token_type: TokenType,
        ttl: timedelta,
    ) -> tuple[str, datetime]:
        now = datetime.now(tz=UTC)
        expires_at = now + ttl
        payload: dict[str, Any] = {
            "sub": subject,
            "type": token_type,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": uuid4().hex,
        }
        if role is not None:
            payload["role"] = role

        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)

        log.debug(
            "[auth.jwt.encode] done",
            type=token_type,
            subject=subject,
            expires_at=expires_at.isoformat(),
        )
        return token, expires_at
