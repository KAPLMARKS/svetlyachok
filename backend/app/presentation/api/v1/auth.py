"""Эндпоинты аутентификации.

POST /api/v1/auth/login    — email + password → access + refresh JWT
POST /api/v1/auth/refresh  — refresh JWT → новая пара токенов

Rate limit: 5/min на /login (защита от брутфорса), 10/min на /refresh.
Превышение → 429 + RFC 7807 + Retry-After (см. middleware/rate_limit.py).

Все ошибки use case'ов (UnauthorizedError) проходят через
exception_handlers.py и превращаются в RFC 7807 Problem Details.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.application.employees.authenticate import (
    LoginCommand,
    LoginUseCase,
    TokenPair,
)
from app.application.employees.refresh_tokens import (
    RefreshCommand,
    RefreshTokensUseCase,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.presentation.dependencies import get_login_use_case, get_refresh_use_case
from app.presentation.middleware.rate_limit import limiter
from app.presentation.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)

log = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# slowapi требует, чтобы decorator'ы получали лимит на момент импорта.
# Берём текущие настройки один раз при загрузке модуля. В тестах
# меняем `settings.auth_login_rate_limit` через monkeypatch до импорта
# (или сбрасываем `limiter._storage` через fixture).
_settings: Settings = get_settings()


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Вход по email + паролю",
    description=(
        "Принимает email и пароль, возвращает пару JWT-токенов. "
        "Rate limit: 5 запросов в минуту на IP."
    ),
)
@limiter.limit(_settings.auth_login_rate_limit)
async def login(
    request: Request,  # обязателен для slowapi.key_func
    payload: LoginRequest,
    use_case: LoginUseCase = Depends(get_login_use_case),
) -> TokenResponse:
    log.debug("[auth.endpoint.login] start", email=payload.email)

    cmd = LoginCommand(
        email=payload.email,
        password=payload.password.get_secret_value(),
    )
    pair: TokenPair = await use_case.execute(cmd)

    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновление access-токена",
    description=(
        "Принимает refresh-токен, возвращает новый access. "
        "Refresh переиспользуется до истечения. Rate limit: 10/мин."
    ),
)
@limiter.limit(_settings.auth_refresh_rate_limit)
async def refresh(
    request: Request,  # обязателен для slowapi.key_func
    payload: RefreshRequest,
    use_case: RefreshTokensUseCase = Depends(get_refresh_use_case),
) -> TokenResponse:
    log.debug("[auth.endpoint.refresh] start")

    cmd = RefreshCommand(refresh_token=payload.refresh_token)
    pair: TokenPair = await use_case.execute(cmd)

    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )
