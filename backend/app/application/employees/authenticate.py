"""Use case аутентификации (POST /api/v1/auth/login).

Алгоритм:

1. Получить Employee по email.
2. Если не найден / неактивен / неверный пароль → один и тот же
   401 `invalid_credentials` (защита от user enumeration).
3. Сгенерировать access + refresh токены через JwtProvider.

Timing-safety: даже если Employee не найден, всё равно вызываем
`hasher.verify(password, DUMMY_HASH)` — иначе по времени ответа
атакующий мог бы отличить «нет такого email» (быстрый ответ) от
«есть, но пароль неверный» (медленный bcrypt-verify).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.logging import get_logger
from app.domain.employees.repositories import EmployeeRepository
from app.domain.employees.services import PasswordHasher
from app.domain.shared.exceptions import UnauthorizedError
from app.infrastructure.auth.jwt_provider import JwtProvider

log = get_logger(__name__)


# Dummy-hash используется для timing-safety при отсутствующем пользователе.
# Хеш ОБЯЗАТЕЛЬНО должен быть валидным bcrypt-hash'ем — иначе checkpw
# поднимет ValueError и вернёт False быстрее, чем на реальном hash'е,
# что создаст timing-leak (атакующий по времени ответа сможет понять
# enumerate'ом, существует ли email).
#
# Генерируется лениво на классе при первом вызове execute, чтобы:
#  1. Не блокировать импорт (bcrypt с rounds=12 — ~250 ms).
#  2. Использовать тот же PasswordHasher, который инжектируется в
#     use case (если когда-нибудь сменим алгоритм — DUMMY_HASH сменится
#     автоматически).


@dataclass(frozen=True)
class LoginCommand:
    """Входные данные для LoginUseCase."""

    email: str
    password: str


@dataclass(frozen=True)
class TokenPair:
    """Результат успешной аутентификации.

    `expires_in` — секунды до истечения access. Клиент использует
    для proactive-refresh (обновлять токен заранее, не дожидаясь 401).
    """

    access_token: str
    refresh_token: str
    expires_in: int


class LoginUseCase:
    """Аутентификация по email + пароль → пара токенов."""

    # Class-level cache: генерируется один раз на процесс при первом
    # execute. Все последующие запросы используют этот же hash — это
    # безопасно, т.к. dummy-hash проверяется только при missing user
    # и его утечка ничему не угрожает.
    _dummy_hash: str | None = None

    def __init__(
        self,
        employee_repo: EmployeeRepository,
        password_hasher: PasswordHasher,
        jwt_provider: JwtProvider,
    ) -> None:
        self._repo = employee_repo
        self._hasher = password_hasher
        self._jwt = jwt_provider

    async def execute(self, cmd: LoginCommand) -> TokenPair:
        log.debug("[auth.login.execute] start", email=cmd.email)

        # Lazy-инициализация валидного dummy-hash при первом вызове.
        # Не делаем это в __init__, чтобы не платить 250 ms на каждый
        # Depends(get_login_use_case) (FastAPI создаёт новый use case
        # на каждый запрос).
        if LoginUseCase._dummy_hash is None:
            LoginUseCase._dummy_hash = self._hasher.hash(
                "timing_attack_dummy_password_for_user_enumeration_protection"
            )

        employee = await self._repo.get_by_email(cmd.email)

        # Timing-safety: всегда тратим bcrypt-цикл, даже если пользователь
        # не найден или неактивен. Иначе атакующий по времени ответа
        # сможет понять, существует ли email в системе.
        password_to_verify = (
            employee.hashed_password if employee is not None else LoginUseCase._dummy_hash
        )
        password_ok = self._hasher.verify(cmd.password, password_to_verify)

        if employee is None:
            log.warning("[auth.login.execute] fail", reason="user_not_found", email=cmd.email)
            raise self._invalid_credentials()
        if not employee.is_active:
            log.warning(
                "[auth.login.execute] fail",
                reason="inactive",
                email=cmd.email,
                employee_id=employee.id,
            )
            raise self._invalid_credentials()
        if not password_ok:
            log.warning(
                "[auth.login.execute] fail",
                reason="wrong_password",
                email=cmd.email,
                employee_id=employee.id,
            )
            raise self._invalid_credentials()

        access_token, access_exp = self._jwt.encode_access_token(
            subject=str(employee.id),
            role=employee.role.value,
        )
        refresh_token, _ = self._jwt.encode_refresh_token(subject=str(employee.id))
        expires_in = max(0, int((access_exp - datetime.now(tz=UTC)).total_seconds()))

        log.info(
            "[auth.login.execute] success",
            employee_id=employee.id,
            role=employee.role.value,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

    @staticmethod
    def _invalid_credentials() -> UnauthorizedError:
        """Единый ответ для всех трёх причин fail.

        Не даём атакующему отличить «нет пользователя» от «неверный пароль»
        от «пользователь деактивирован». Реальная причина видна только
        в server-side логах оператора.
        """
        return UnauthorizedError(
            code="invalid_credentials",
            message="Неверный email или пароль",
        )
