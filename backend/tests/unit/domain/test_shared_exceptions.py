"""Unit-тесты доменных исключений."""

from __future__ import annotations

import pytest

from app.domain.shared.exceptions import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


pytestmark = pytest.mark.unit


def test_app_error_default_status() -> None:
    err = AppError("something failed")
    assert err.status_code == 500
    assert err.code == "app_error"
    assert err.message == "something failed"
    assert err.details == {}


def test_validation_error_status_code() -> None:
    err = ValidationError("invalid email", code="invalid_email")
    assert err.status_code == 400
    assert err.code == "invalid_email"


def test_not_found_error_status_code() -> None:
    err = NotFoundError("employee not found", code="employee_not_found")
    assert err.status_code == 404
    assert err.code == "employee_not_found"


def test_conflict_error_status_code() -> None:
    err = ConflictError("duplicate email")
    assert err.status_code == 409
    assert err.code == "conflict"  # default


def test_unauthorized_error_status_code() -> None:
    err = UnauthorizedError("missing token")
    assert err.status_code == 401


def test_forbidden_error_status_code() -> None:
    err = ForbiddenError("admin role required")
    assert err.status_code == 403


def test_app_error_carries_details() -> None:
    err = ValidationError(
        "field too long",
        code="too_long",
        details={"field": "name", "max_length": 100},
    )
    assert err.details == {"field": "name", "max_length": 100}


def test_app_error_repr_includes_code_and_status() -> None:
    err = NotFoundError("not found")
    s = repr(err)
    assert "NotFoundError" in s
    assert "not_found" in s
    assert "404" in s
