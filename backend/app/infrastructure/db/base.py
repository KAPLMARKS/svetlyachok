"""DeclarativeBase, naming convention для constraint'ов и общие миксины ORM.

Все ORM-модели наследуются от `Base`. Naming convention важен для
предсказуемого поведения `alembic revision --autogenerate`: иначе
имена индексов и constraint'ов берутся из адресов объектов и меняются
от запуска к запуску, генерируя «фейковые» миграции.

Convention следует рекомендациям SQLAlchemy/Alembic:
https://alembic.sqlalchemy.org/en/latest/naming.html
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from sqlalchemy import BigInteger, DateTime, Identity, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming convention: ix_*, uq_*, ck_*, fk_*, pk_* — стандартные префиксы.
# При autogenerate Alembic будет порождать стабильные имена constraint'ов.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Базовый класс всех ORM-моделей.

    Все модели проекта наследуются от него. metadata содержит naming
    convention, что критично для стабильного autogenerate миграций.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Подмешивает столбцы created_at / updated_at со server-side defaults.

    `server_default=func.now()` — Postgres сам ставит timestamp при INSERT,
    клиент не отправляет значение. Это безопасно при высокой конкурентности
    и не зависит от часов клиента.

    `onupdate=func.now()` — при UPDATE updated_at автоматически обновляется.
    SQLAlchemy транслирует это в `UPDATE ... SET updated_at = now() ...`.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Type alias для BigInt PK с identity-генератором.
# Использовать как `id: Mapped[BigIntPK]` в моделях, чтобы не повторять
# `BigInteger, Identity(always=False), primary_key=True` в каждой таблице.
BigIntPK = Annotated[
    int,
    mapped_column(BigInteger, Identity(always=False), primary_key=True),
]
