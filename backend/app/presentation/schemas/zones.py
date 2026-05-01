"""Pydantic-схемы CRUD зон."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.zones.entities import ZoneType

# HEX-цвет вида #RRGGBB. Тот же regex используется в БД CHECK constraint.
_HEX_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"


class ZoneCreateRequest(BaseModel):
    """POST /api/v1/zones — admin создаёт зону."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    type: ZoneType
    description: str | None = None
    display_color: str | None = Field(default=None, pattern=_HEX_COLOR_PATTERN)


class ZoneUpdateRequest(BaseModel):
    """PATCH /api/v1/zones/{id} — все поля опциональны."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: ZoneType | None = None
    description: str | None = None
    display_color: str | None = Field(default=None, pattern=_HEX_COLOR_PATTERN)
    # Явные флаги для очистки опциональных полей.
    clear_description: bool = False
    clear_display_color: bool = False


class ZoneResponse(BaseModel):
    """Публичная информация о зоне."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    type: str
    description: str | None = None
    display_color: str | None = None


class ZonesPageResponse(BaseModel):
    """Страница зон с пагинацией."""

    model_config = ConfigDict(extra="forbid")

    items: list[ZoneResponse]
    total: int
    limit: int
    offset: int
