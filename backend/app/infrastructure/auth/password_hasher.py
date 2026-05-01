"""bcrypt-реализация PasswordHasher.

Используем нативный пакет `bcrypt`, без passlib (passlib имеет известные
проблемы совместимости с bcrypt 4+ — fail на чтении внутреннего атрибута
__about__.__version__, проще брать bcrypt напрямую).

Параметры:
- work_factor=12 — рекомендация OWASP 2024. ~250 ms/попытка на современном
  x86_64 CPU; защита от брутфорса.
- bcrypt.checkpw — constant-time сравнение на уровне C; безопасно от
  timing-attack по байтам hash'а.
"""

from __future__ import annotations

import bcrypt

from app.core.logging import get_logger
from app.domain.employees.services import PasswordHasher

log = get_logger(__name__)

# OWASP 2024: 12 раундов = ~250ms/попытка. При 14 — ~1s, что замедляет
# легитимный логин и не сильно усиливает защиту против современного
# железа атакующего.
_DEFAULT_WORK_FACTOR = 12


class BcryptPasswordHasher(PasswordHasher):
    """Хешер на bcrypt с фиксированным work factor.

    Stateless — потокобезопасен. Можно использовать как singleton.
    """

    def __init__(self, work_factor: int = _DEFAULT_WORK_FACTOR) -> None:
        if work_factor < 10:
            raise ValueError(
                f"bcrypt work_factor должен быть >= 10 (OWASP), получено {work_factor}"
            )
        self._work_factor = work_factor

    def hash(self, plain: str) -> str:
        """Возвращает bcrypt-hash в utf-8.

        Bcrypt гарантирует уникальный hash при каждом вызове даже для
        одного и того же plain — соль генерируется при каждом hash'е.
        """
        if not isinstance(plain, str):
            raise TypeError("plain password must be str")

        hashed = bcrypt.hashpw(
            plain.encode("utf-8"),
            bcrypt.gensalt(rounds=self._work_factor),
        )
        result = hashed.decode("utf-8")

        log.debug(
            "[auth.password_hasher.hash] hashed",
            length=len(result),
            rounds=self._work_factor,
        )
        return result

    def verify(self, plain: str, hashed: str) -> bool:
        """Constant-time проверка пароля.

        Возвращает False при битом hash'е (ValueError в bcrypt) — это
        важно для двух кейсов:
          - SQL-injection попытка с мусорным hash'ем не должна крашить
            процесс auth;
          - dummy-hash для timing-safety (LoginUseCase) гарантированно
            не пройдёт verify.
        """
        if not isinstance(plain, str) or not isinstance(hashed, str):
            log.debug(
                "[auth.password_hasher.verify] type_mismatch",
                plain_type=type(plain).__name__,
                hashed_type=type(hashed).__name__,
            )
            return False

        try:
            ok = bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError as exc:
            # Битый bcrypt-hash (например, из старой версии или мусор).
            # checkpw кидает ValueError, что важно для timing-safety:
            # бракованный hash отрабатывает быстро, нелегитимный пользователь
            # это заметит. Но для текущей задачи (`get_by_email -> None`)
            # мы используем DUMMY_HASH из BcryptPasswordHasher().hash(...),
            # который всегда валиден.
            log.debug(
                "[auth.password_hasher.verify] invalid_hash",
                exc_type=type(exc).__name__,
            )
            return False

        log.debug(
            "[auth.password_hasher.verify] result",
            result="ok" if ok else "fail",
        )
        return bool(ok)
