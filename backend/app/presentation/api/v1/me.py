"""Защищённый эндпоинт «информация о себе».

GET /api/v1/me — возвращает данные текущего аутентифицированного
сотрудника. Требует валидный Bearer access-токен.

Используется как:
1. Smoke-проверка авторизации после login (mobile/web проверяют, что
   токен действует).
2. Отображение профиля в UI (имя, роль, расписание).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.logging import get_logger
from app.domain.employees.entities import Employee
from app.presentation.dependencies import get_current_user
from app.presentation.schemas.auth import CurrentUserResponse

log = get_logger(__name__)

router = APIRouter(prefix="/me", tags=["users"])


@router.get(
    "",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Текущий пользователь",
    description="Возвращает данные аутентифицированного пользователя по access-токену.",
)
async def get_me(
    current_user: Employee = Depends(get_current_user),
) -> CurrentUserResponse:
    log.debug("[me.get] employee_id={id}", id=current_user.id)
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
    )
