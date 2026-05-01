"""Pydantic-схемы эндпоинтов аутентификации.

Все модели — `extra="forbid"`, чтобы клиенты не могли пробросить
лишних полей (например, `is_admin: true` в LoginRequest).

`password` хранится в `SecretStr` — Pydantic автоматически маскирует
его в repr/str/`model_dump()`, что защищает от случайного появления
пароля в логах через стандартное логирование request body.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login — вход по email + паролю."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(
        ...,
        description="Email сотрудника. Используется как login.",
        examples=["admin@svetlyachok.local"],
    )
    password: SecretStr = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Пароль. Минимум 8 символов.",
    )


class RefreshRequest(BaseModel):
    """POST /api/v1/auth/refresh — обмен refresh-токена на новый access."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(
        ...,
        min_length=10,
        description="Refresh-токен, полученный из /auth/login.",
    )


class TokenResponse(BaseModel):
    """Ответ на /auth/login и /auth/refresh — пара токенов."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105  — OAuth2 schema name, not a password
    expires_in: int = Field(..., description="Секунды до истечения access-токена.")


class CurrentUserResponse(BaseModel):
    """Ответ на GET /api/v1/me — публичная информация о текущем пользователе.

    Намеренно НЕ содержит `hashed_password` — даже маскированный hash
    наружу не выдаём (это правило Clean Architecture: domain-сущность
    Employee имеет hashed_password, presentation-слой её не пробрасывает).
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
