"""Use case обновления токенов (POST /api/v1/auth/refresh).

Принимает refresh-токен → возвращает новый access (refresh оставляем
прежний для упрощения mobile-кэша; rotation добавим вместе с
blacklist'ом jti на следующих итерациях).

При получении claims проверяем актуальность пользователя в БД:
если he был деактивирован после выпуска токена — выдавать новый
access нельзя.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.employees.authenticate import TokenPair
from app.core.logging import get_logger
from app.domain.employees.repositories import EmployeeRepository
from app.domain.shared.exceptions import UnauthorizedError
from app.infrastructure.auth.jwt_provider import JwtProvider

log = get_logger(__name__)


@dataclass(frozen=True)
class RefreshCommand:
    """Входные данные для RefreshTokensUseCase."""

    refresh_token: str


class RefreshTokensUseCase:
    """Обмен refresh-токена на новый access (refresh переиспользуется)."""

    def __init__(
        self,
        employee_repo: EmployeeRepository,
        jwt_provider: JwtProvider,
    ) -> None:
        self._repo = employee_repo
        self._jwt = jwt_provider

    async def execute(self, cmd: RefreshCommand) -> TokenPair:
        # decode сам поднимет UnauthorizedError(invalid_token | expired_token | wrong_token_type)
        claims = self._jwt.decode(cmd.refresh_token, expected_type="refresh")

        log.debug("[auth.refresh.execute] start", subject=claims.sub)

        try:
            employee_id = int(claims.sub)
        except (TypeError, ValueError) as exc:
            log.warning(
                "[auth.refresh.execute] fail",
                reason="invalid_subject",
                subject=claims.sub,
            )
            raise UnauthorizedError(
                code="invalid_token",
                message="Недействительный токен",
            ) from exc

        employee = await self._repo.get_by_id(employee_id)
        if employee is None:
            log.warning(
                "[auth.refresh.execute] fail",
                reason="user_not_found",
                subject=claims.sub,
            )
            raise UnauthorizedError(
                code="user_not_found",
                message="Пользователь не найден",
            )
        if not employee.is_active:
            log.warning(
                "[auth.refresh.execute] fail",
                reason="user_disabled",
                employee_id=employee.id,
            )
            raise UnauthorizedError(
                code="user_disabled",
                message="Учётная запись отключена",
            )

        access_token, access_exp = self._jwt.encode_access_token(
            subject=str(employee.id),
            role=employee.role.value,
        )
        # Refresh не ротируется — клиент продолжает использовать старый
        # до его истечения. Rotation + blacklist jti — открытый вопрос
        # (см. план).
        expires_in = max(0, int((access_exp - datetime.now(tz=UTC)).total_seconds()))

        log.info(
            "[auth.refresh.execute] success",
            employee_id=employee.id,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=cmd.refresh_token,
            expires_in=expires_in,
        )
