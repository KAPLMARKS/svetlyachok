"""Общие FastAPI-зависимости для presentation-слоя.

Composition root: связывает Protocol'ы из domain/application с
конкретными реализациями из infrastructure через FastAPI Depends().
Это позволяет тестам подменять реализации через
`app.dependency_overrides[...]` без monkey-patch'а module-level переменных.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.employees.authenticate import LoginUseCase
from app.application.employees.refresh_tokens import RefreshTokensUseCase
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.employees.entities import Employee, Role
from app.domain.employees.repositories import EmployeeRepository
from app.domain.employees.services import PasswordHasher
from app.domain.shared.exceptions import ForbiddenError, UnauthorizedError
from app.infrastructure.auth import BcryptPasswordHasher, JwtProvider
from app.infrastructure.db.session import get_session, get_sessionmaker
from app.infrastructure.repositories.employees_repository import (
    SqlAlchemyEmployeeRepository,
)

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# БД и инфраструктура
# ---------------------------------------------------------------------------


def get_db_sessionmaker_dep() -> async_sessionmaker[AsyncSession]:
    """FastAPI dependency: возвращает текущую фабрику AsyncSession.

    Используется компонентами, которым нужна именно фабрика (например,
    healthcheck открывает свою короткую сессию). Транзакционная сессия
    для CRUD-роутов берётся через `get_session` из infrastructure.
    """
    return get_sessionmaker()


# ---------------------------------------------------------------------------
# Аутентификация: примитивы и use cases
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _password_hasher_singleton() -> BcryptPasswordHasher:
    """Singleton bcrypt-хешера: stateless, можно переиспользовать."""
    return BcryptPasswordHasher()


def get_password_hasher() -> PasswordHasher:
    """FastAPI dependency: bcrypt-хешер."""
    return _password_hasher_singleton()


def get_jwt_provider(
    settings: Settings = Depends(get_settings),
) -> JwtProvider:
    """FastAPI dependency: JWT-провайдер с актуальными настройками."""
    return JwtProvider(settings)


def get_employee_repository(
    session: AsyncSession = Depends(get_session),
) -> EmployeeRepository:
    """FastAPI dependency: репозиторий сотрудников.

    Зависит от транзакционной сессии — read-only-операции корректно
    закроют без commit'а.
    """
    return SqlAlchemyEmployeeRepository(session)


def get_login_use_case(
    repo: EmployeeRepository = Depends(get_employee_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
    jwt: JwtProvider = Depends(get_jwt_provider),
) -> LoginUseCase:
    """FastAPI dependency: сборка LoginUseCase."""
    return LoginUseCase(employee_repo=repo, password_hasher=hasher, jwt_provider=jwt)


def get_refresh_use_case(
    repo: EmployeeRepository = Depends(get_employee_repository),
    jwt: JwtProvider = Depends(get_jwt_provider),
) -> RefreshTokensUseCase:
    """FastAPI dependency: сборка RefreshTokensUseCase."""
    return RefreshTokensUseCase(employee_repo=repo, jwt_provider=jwt)


# ---------------------------------------------------------------------------
# Защита роутов: текущий пользователь и role-based access
# ---------------------------------------------------------------------------


# auto_error=False — мы сами возвращаем UnauthorizedError с RFC 7807
# через app/presentation/exception_handlers.py; стандартный
# `HTTPException(401)` от HTTPBearer выглядел бы иначе.
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    jwt: JwtProvider = Depends(get_jwt_provider),
    repo: EmployeeRepository = Depends(get_employee_repository),
) -> Employee:
    """FastAPI dependency: возвращает аутентифицированного Employee.

    Алгоритм:
    1. Извлечь Bearer-токен из заголовка Authorization.
    2. Декодировать access-токен (jwt.decode сам поднимет
       UnauthorizedError при невалидном/истёкшем).
    3. Найти Employee по claims.sub (employee_id).
    4. Проверить is_active — деактивированный пользователь не имеет
       права работать, даже если у него на руках валидный токен.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        log.warning("[auth.deps.current_user] fail", reason="missing")
        raise UnauthorizedError(
            code="missing_token",
            message="Требуется заголовок Authorization: Bearer <token>",
        )

    claims = jwt.decode(credentials.credentials, expected_type="access")

    try:
        employee_id = int(claims.sub)
    except (TypeError, ValueError) as exc:
        log.warning(
            "[auth.deps.current_user] fail",
            reason="invalid_subject",
            subject=claims.sub,
        )
        raise UnauthorizedError(
            code="invalid_token",
            message="Недействительный токен",
        ) from exc

    employee = await repo.get_by_id(employee_id)
    if employee is None:
        log.warning(
            "[auth.deps.current_user] fail",
            reason="user_not_found",
            employee_id=employee_id,
        )
        raise UnauthorizedError(
            code="user_not_found",
            message="Пользователь не найден",
        )
    if not employee.is_active:
        log.warning(
            "[auth.deps.current_user] fail",
            reason="user_disabled",
            employee_id=employee.id,
        )
        raise UnauthorizedError(
            code="user_disabled",
            message="Учётная запись отключена",
        )

    log.debug(
        "[auth.deps.current_user] resolved",
        employee_id=employee.id,
        role=employee.role.value,
    )
    return employee


def require_role(*allowed_roles: Role) -> Callable[..., Employee]:
    """Фабрика dependency для role-based авторизации.

    Использование:
        @router.get(
            "/admin/something",
            dependencies=[Depends(require_role(Role.ADMIN))],
        )
        async def handler(...): ...

    или с инъекцией Employee:
        async def handler(user: Employee = Depends(require_role(Role.ADMIN))): ...
    """
    if not allowed_roles:
        raise ValueError("require_role требует хотя бы одну роль")

    async def _checker(user: Employee = Depends(get_current_user)) -> Employee:
        if user.role not in allowed_roles:
            log.warning(
                "[auth.deps.require_role] denied",
                employee_id=user.id,
                required=[r.value for r in allowed_roles],
                actual=user.role.value,
            )
            raise ForbiddenError(
                code="insufficient_role",
                message="Недостаточно прав для этого действия",
                details={
                    "required": [r.value for r in allowed_roles],
                    "actual": user.role.value,
                },
            )
        return user

    return _checker
