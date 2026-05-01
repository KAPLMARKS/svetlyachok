"""Доменные сущности модуля зон.

Domain не знает об ORM — `Zone` живёт независимо от SQLAlchemy. Маппер
ORM↔domain — забота infrastructure-репозитория.

`ZoneType` зеркалит ORM-enum (значения совпадают строка-в-строку),
но импортов из infrastructure нет — это запрет Clean Architecture.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace


class ZoneType(str, enum.Enum):
    """Тип зоны для классификации позиции.

    Совпадает с метриками ISO/IEC 18305:2016 — Detection Probability
    считается отдельно по каждому типу.
    """

    WORKPLACE = "workplace"
    CORRIDOR = "corridor"
    MEETING_ROOM = "meeting_room"
    OUTSIDE_OFFICE = "outside_office"


@dataclass(frozen=True)
class Zone:
    """Зона учёта посещаемости (помещение/область).

    Frozen: после получения из репозитория мутировать нельзя; любое
    изменение проходит через use case → новый Zone → save в repo.
    """

    id: int
    name: str
    type: ZoneType
    description: str | None = None
    display_color: str | None = None

    def with_changes(
        self,
        *,
        name: str | None = None,
        type: ZoneType | None = None,  # noqa: A002 — поле модели
        description: str | None = None,
        display_color: str | None = None,
        clear_description: bool = False,
        clear_display_color: bool = False,
    ) -> Zone:
        """Возвращает копию Zone с применёнными изменениями.

        None в опциональных полях `description` и `display_color`
        неоднозначен («не менять» vs «очистить»), поэтому очистка
        выражается через явные флаги `clear_*`.
        """
        return replace(
            self,
            name=name if name is not None else self.name,
            type=type if type is not None else self.type,
            description=(
                None
                if clear_description
                else (description if description is not None else self.description)
            ),
            display_color=(
                None
                if clear_display_color
                else (
                    display_color
                    if display_color is not None
                    else self.display_color
                )
            ),
        )
