"""Эндпоинты CRUD сотрудников.

Матрица доступа:

| Эндпоинт                                     | Admin | Self | Other employee |
|----------------------------------------------|-------|------|----------------|
| POST   /employees                            | OK    | 403  | 403            |
| GET    /employees                            | OK    | 403  | 403            |
| GET    /employees/{id}                       | OK    | OK   | 403            |
| PATCH  /employees/{id}                       | OK*   | OK** | 403            |
| POST   /employees/{id}/password              | OK*** | OK** | 403            |
| POST   /employees/{id}/deactivate            | OK    | 403  | 403            |
| POST   /employees/{id}/activate              | OK    | 403  | 403            |

Примечания:
- (*)   admin может менять role/schedule/full_name; деактивацию делать
        через специальный endpoint
- (**)  self может менять только свой full_name; role/schedule запрещены
- (***) admin сбрасывает чужой пароль без old_password; self меняет
        свой только с правильным old_password

Все ошибки use case'ов (UnauthorizedError, ForbiddenError, ConflictError,
NotFoundError) проходят через существующий exception handler и
превращаются в RFC 7807.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.application.employees.change_password import (
    ChangePasswordCommand,
    ChangePasswordUseCase,
)
from app.application.employees.create_employee import (
    CreateEmployeeCommand,
    CreateEmployeeUseCase,
)
from app.application.employees.deactivate_employee import (
    ActivateEmployeeCommand,
    ActivateEmployeeUseCase,
    DeactivateEmployeeCommand,
    DeactivateEmployeeUseCase,
)
from app.application.employees.list_employees import (
    ListEmployeesQuery,
    ListEmployeesUseCase,
)
from app.application.employees.update_employee import (
    UpdateEmployeeCommand,
    UpdateEmployeeUseCase,
)
from app.core.logging import get_logger
from app.domain.employees.entities import Employee, Role
from app.domain.employees.repositories import EmployeeRepository
from app.domain.shared.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.presentation.dependencies import (
    get_activate_employee_use_case,
    get_change_password_use_case,
    get_create_employee_use_case,
    get_current_user,
    get_deactivate_employee_use_case,
    get_employee_repository,
    get_list_employees_use_case,
    get_update_employee_use_case,
    require_role,
)
from app.presentation.schemas.employees import (
    ChangePasswordRequest,
    EmployeeCreateRequest,
    EmployeeResponse,
    EmployeesPageResponse,
    EmployeeUpdateRequest,
)

log = get_logger(__name__)

router = APIRouter(prefix="/employees", tags=["employees"])


def _to_response(employee: Employee) -> EmployeeResponse:
    """Доменный Employee → API DTO без hashed_password."""
    return EmployeeResponse(
        id=employee.id,
        email=employee.email,
        full_name=employee.full_name,
        role=employee.role.value,
        is_active=employee.is_active,
        schedule_start=employee.schedule_start,
        schedule_end=employee.schedule_end,
    )


# ---------------------------------------------------------------------------
# Admin-only: создать / список
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать сотрудника (admin)",
)
async def create_employee(
    payload: EmployeeCreateRequest,
    _: Employee = Depends(require_role(Role.ADMIN)),
    use_case: CreateEmployeeUseCase = Depends(get_create_employee_use_case),
) -> EmployeeResponse:
    log.debug("[employees.endpoint.create] start", email=payload.email)

    cmd = CreateEmployeeCommand(
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        initial_password=payload.initial_password.get_secret_value(),
        schedule_start=payload.schedule_start,
        schedule_end=payload.schedule_end,
    )
    employee = await use_case.execute(cmd)
    return _to_response(employee)


@router.get(
    "",
    response_model=EmployeesPageResponse,
    summary="Список сотрудников (admin)",
)
async def list_employees(
    role: Role | None = Query(default=None, description="Фильтр по роли"),
    is_active: bool | None = Query(
        default=None, description="Фильтр по активности"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: Employee = Depends(require_role(Role.ADMIN)),
    use_case: ListEmployeesUseCase = Depends(get_list_employees_use_case),
) -> EmployeesPageResponse:
    log.debug(
        "[employees.endpoint.list] start",
        role=role.value if role else None,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )

    page = await use_case.execute(
        ListEmployeesQuery(
            role=role,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )
    )
    return EmployeesPageResponse(
        items=[_to_response(e) for e in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


# ---------------------------------------------------------------------------
# Self или admin: получить / обновить / сменить пароль
# ---------------------------------------------------------------------------


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Получить сотрудника по id (admin или self)",
)
async def get_employee(
    employee_id: int,
    current_user: Employee = Depends(get_current_user),
    repo: EmployeeRepository = Depends(get_employee_repository),
) -> EmployeeResponse:
    """Self или admin. Для self-кейса возвращаем уже резолвленный
    `current_user` без лишнего SQL. Для admin — короткий select по id.
    """
    log.debug(
        "[employees.endpoint.get] start",
        employee_id=employee_id,
        current_user_id=current_user.id,
    )

    if not current_user.is_admin() and current_user.id != employee_id:
        raise ForbiddenError(
            code="cannot_view_other_employee",
            message="Можно просматривать только свой профиль",
        )

    if current_user.id == employee_id:
        return _to_response(current_user)

    employee = await repo.get_by_id(employee_id)
    if employee is None:
        raise NotFoundError(
            code="employee_not_found",
            message=f"Сотрудник с id={employee_id} не найден",
        )
    return _to_response(employee)


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Обновить сотрудника (admin полностью; self только full_name)",
)
async def update_employee(
    employee_id: int,
    payload: EmployeeUpdateRequest,
    current_user: Employee = Depends(get_current_user),
    use_case: UpdateEmployeeUseCase = Depends(get_update_employee_use_case),
) -> EmployeeResponse:
    log.debug(
        "[employees.endpoint.update] start",
        employee_id=employee_id,
        current_user_id=current_user.id,
    )

    is_self = current_user.id == employee_id
    if not current_user.is_admin() and not is_self:
        raise ForbiddenError(
            code="cannot_update_other_employee",
            message="Можно обновлять только свой профиль",
        )

    # Self может менять только full_name. Любая попытка передать
    # role/schedule_* со стороны не-admin — 403.
    if not current_user.is_admin():
        forbidden_fields = []
        if payload.role is not None:
            forbidden_fields.append("role")
        if (
            payload.schedule_start is not None
            or payload.clear_schedule_start
            or payload.schedule_end is not None
            or payload.clear_schedule_end
        ):
            forbidden_fields.append("schedule_*")
        if forbidden_fields:
            raise ForbiddenError(
                code="cannot_modify_admin_fields",
                message=(
                    "Сотрудник может менять только свой full_name. "
                    f"Поля {forbidden_fields} доступны только администратору."
                ),
            )

    cmd = UpdateEmployeeCommand(
        employee_id=employee_id,
        full_name=payload.full_name,
        role=payload.role,
        schedule_start=payload.schedule_start,
        schedule_end=payload.schedule_end,
        clear_schedule_start=payload.clear_schedule_start,
        clear_schedule_end=payload.clear_schedule_end,
    )
    employee = await use_case.execute(cmd)
    return _to_response(employee)


@router.post(
    "/{employee_id}/password",
    response_model=EmployeeResponse,
    summary="Сменить пароль (admin reset или self change)",
)
async def change_password(
    employee_id: int,
    payload: ChangePasswordRequest,
    current_user: Employee = Depends(get_current_user),
    use_case: ChangePasswordUseCase = Depends(get_change_password_use_case),
) -> EmployeeResponse:
    log.debug(
        "[employees.endpoint.change_password] start",
        employee_id=employee_id,
        current_user_id=current_user.id,
    )

    is_self = current_user.id == employee_id
    is_admin = current_user.is_admin()

    if not is_admin and not is_self:
        raise ForbiddenError(
            code="cannot_change_other_password",
            message="Можно менять только свой пароль",
        )

    is_admin_reset = is_admin and not is_self
    if not is_admin_reset and payload.old_password is None:
        raise ValidationError(
            code="old_password_required",
            message="Для смены своего пароля требуется указать старый",
        )

    cmd = ChangePasswordCommand(
        employee_id=employee_id,
        new_password=payload.new_password.get_secret_value(),
        old_password=(
            payload.old_password.get_secret_value()
            if payload.old_password is not None
            else None
        ),
        is_admin_reset=is_admin_reset,
    )
    employee = await use_case.execute(cmd)
    return _to_response(employee)


# ---------------------------------------------------------------------------
# Admin-only: deactivate / activate
# ---------------------------------------------------------------------------


@router.post(
    "/{employee_id}/deactivate",
    response_model=EmployeeResponse,
    summary="Деактивировать сотрудника (admin)",
)
async def deactivate_employee(
    employee_id: int,
    current_user: Employee = Depends(require_role(Role.ADMIN)),
    use_case: DeactivateEmployeeUseCase = Depends(get_deactivate_employee_use_case),
) -> EmployeeResponse:
    log.debug(
        "[employees.endpoint.deactivate] start",
        employee_id=employee_id,
        current_user_id=current_user.id,
    )
    cmd = DeactivateEmployeeCommand(
        employee_id=employee_id,
        current_user_id=current_user.id,
    )
    employee = await use_case.execute(cmd)
    return _to_response(employee)


@router.post(
    "/{employee_id}/activate",
    response_model=EmployeeResponse,
    summary="Реактивировать сотрудника (admin)",
)
async def activate_employee(
    employee_id: int,
    _: Employee = Depends(require_role(Role.ADMIN)),
    use_case: ActivateEmployeeUseCase = Depends(get_activate_employee_use_case),
) -> EmployeeResponse:
    log.debug(
        "[employees.endpoint.activate] start", employee_id=employee_id
    )
    cmd = ActivateEmployeeCommand(employee_id=employee_id)
    employee = await use_case.execute(cmd)
    return _to_response(employee)
