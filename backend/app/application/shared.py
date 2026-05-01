"""Кросс-модульные DTO application-слоя.

Сейчас содержит только generic Page для пагинации. Если application
получит больше переиспользуемых DTO — расширим этот модуль.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):  # noqa: UP046  — PEP 695 синтаксис плохо дружит с frozen dataclass на 3.12
    """Generic-страница списка с пагинацией.

    Использование:
        Page[Employee](items=[...], total=42, limit=50, offset=0)
    """

    items: list[T]
    total: int
    limit: int
    offset: int
