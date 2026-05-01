"""Точка входа FastAPI приложения.

Запуск: `uvicorn app.main:app --port 8000 --reload`

Композиция:
1. Загрузка настроек (pydantic-settings)
2. Инициализация structlog
3. Создание FastAPI app
4. Подключение middleware (CORS, CorrelationId)
5. Регистрация exception handlers
6. Подключение API routers (v1)

Принцип: fail fast при ошибке инициализации (не запускаемся в кривом состоянии).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.db.session import dispose_engine, init_engine
from app.presentation.api.v1.attendance import router as attendance_router
from app.presentation.api.v1.auth import router as auth_router
from app.presentation.api.v1.calibration import router as calibration_router
from app.presentation.api.v1.employees import router as employees_router
from app.presentation.api.v1.fingerprints import router as fingerprints_router
from app.presentation.api.v1.health import router as health_router
from app.presentation.api.v1.me import router as me_router
from app.presentation.api.v1.positioning import router as positioning_router
from app.presentation.api.v1.zones import router as zones_router
from app.presentation.exception_handlers import register_exception_handlers
from app.presentation.middleware.correlation_id import CorrelationIdMiddleware
from app.presentation.middleware.rate_limit import limiter, rate_limit_exceeded_handler


def create_app() -> FastAPI:
    """Фабрика приложения.

    Возвращает готовый FastAPI с подключёнными middleware, routers, handlers.
    """
    log = get_logger(__name__)

    try:
        settings = get_settings()
    except Exception:
        # Логирование может быть ещё не настроено, но get_logger использует
        # дефолтную конфигурацию stdlib — что-то увидим
        log.error("[main.create_app] failed to load settings", exc_info=True)
        raise

    configure_logging(settings)

    log.debug(
        "[main.create_app] start",
        environment=settings.environment,
        log_level=settings.log_level,
        log_format=settings.log_format,
    )

    app = FastAPI(
        title=settings.app_name,
        version=_app_version(),
        description="REST API для АИС «Светлячок» — indoor-позиционирование по Wi-Fi RSSI",
        lifespan=_lifespan,
    )

    # Middleware (порядок важен: CORS снаружи, CorrelationId внутри)
    app.add_middleware(CorrelationIdMiddleware)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.cors_origins],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Correlation-ID"],
        )

    # Exception handlers (RFC 7807)
    register_exception_handlers(app)

    # Rate limiter — slowapi требует app.state.limiter, отдельный handler
    # на RateLimitExceeded.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Routers
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(me_router, prefix="/api/v1")
    app.include_router(employees_router, prefix="/api/v1")
    app.include_router(zones_router, prefix="/api/v1")
    app.include_router(fingerprints_router, prefix="/api/v1")
    app.include_router(calibration_router, prefix="/api/v1")
    app.include_router(positioning_router, prefix="/api/v1")
    app.include_router(attendance_router, prefix="/api/v1")

    log.info(
        "[main.create_app] ready",
        version=_app_version(),
        environment=settings.environment,
        routers=[
            "/api/v1/health",
            "/api/v1/auth",
            "/api/v1/me",
            "/api/v1/employees",
            "/api/v1/zones",
            "/api/v1/fingerprints",
            "/api/v1/calibration",
            "/api/v1/positioning",
            "/api/v1/attendance",
        ],
        middleware=[
            "CorrelationIdMiddleware",
            *(["CORSMiddleware"] if settings.cors_origins else []),
        ],
    )

    return app


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Lifespan-хук FastAPI — startup и shutdown.

    На startup — инициализирует пул соединений к БД (engine создаётся
    lazy: реальное TCP-подключение установится при первом запросе).
    На shutdown — корректно закрывает пул.

    Engine создаётся даже если БД недоступна — это намеренно. Сервер
    должен подняться, healthcheck покажет `database: fail`, а оператор
    увидит проблему и поднимет БД. Иначе пришлось бы рестартовать
    приложение каждый раз при сбое БД.
    """
    log = get_logger(__name__)
    settings = get_settings()

    log.info("[main.lifespan] startup begin")
    try:
        init_engine(settings)
        log.info("[main.lifespan] db engine ready")
    except Exception:
        log.error("[main.lifespan] startup failed", exc_info=True)
        raise

    log.info("[main.lifespan] startup complete")
    try:
        yield
    finally:
        log.info("[main.lifespan] shutdown begin")
        await dispose_engine()
        log.info("[main.lifespan] db engine disposed")
        log.info("[main.lifespan] shutdown complete")


def _app_version() -> str:
    """Возвращает версию пакета."""
    try:
        return version("svetlyachok-backend")
    except PackageNotFoundError:
        return "0.0.0-dev"


# Module-level app для `uvicorn app.main:app`
app = create_app()


def _settings_for_uvicorn() -> Settings:
    """Helper для тестов и других потребителей module-level state."""
    return get_settings()
