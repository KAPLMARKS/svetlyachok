"""Rate limiting на /auth-эндпоинты через slowapi.

Стратегия:
- Один глобальный `Limiter` инстанс с in-memory storage. Для пилота
  достаточно — backend в одном процессе. При горизонтальном
  масштабировании (несколько uvicorn worker'ов) перейдём на Redis-storage
  через `slowapi.Limiter(storage_uri="redis://...")`.
- Ключ — IP клиента из `request.client.host`. Если за reverse proxy —
  включить TRUST_PROXY (работа с X-Forwarded-For в slowapi).
- Превышение → 429 Too Many Requests + RFC 7807 + заголовок Retry-After.

Применение в роутах:

    @router.post("/login")
    @limiter.limit(settings.auth_login_rate_limit)
    async def login(request: Request, ...):
        ...

`request: Request` обязательно в сигнатуре эндпоинта — slowapi
извлекает IP именно из него.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.logging import get_logger

log = get_logger(__name__)


# Глобальный singleton — slowapi требует один Limiter на приложение.
# В тестах сбрасываем storage через `limiter.reset()` (см. conftest).
limiter = Limiter(key_func=get_remote_address)


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    """RFC 7807 Problem Details для 429.

    `Retry-After` — рекомендация HTTP/1.1: клиент должен подождать
    указанное число секунд перед повторной попыткой. slowapi кладёт
    `retry_after` в `exc.detail`.
    """
    log.warning(
        "[auth.rate_limit] exceeded",
        path=request.url.path,
        ip=get_remote_address(request),
        limit=str(exc.detail),
    )

    # exc.detail у slowapi — строка вида "5 per 1 minute"; реального
    # retry-after-числа в API нет. Берём `_default_retry_after` из
    # exc.headers если оно там есть, иначе fallback 60 секунд.
    retry_after = getattr(exc, "headers", {}).get("Retry-After", "60")

    return JSONResponse(
        status_code=429,
        content={
            "type": "about:blank",
            "title": "Too Many Requests",
            "status": 429,
            "code": "rate_limit_exceeded",
            "detail": f"Превышен лимит запросов: {exc.detail}",
            "instance": str(request.url.path),
        },
        headers={"Retry-After": str(retry_after)},
    )
