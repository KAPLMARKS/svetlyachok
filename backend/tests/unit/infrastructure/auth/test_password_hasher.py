"""Unit-тесты bcrypt-хешера."""

from __future__ import annotations

import pytest

from app.infrastructure.auth.password_hasher import BcryptPasswordHasher

pytestmark = pytest.mark.unit


@pytest.fixture
def hasher() -> BcryptPasswordHasher:
    """Хешер с дефолтным work_factor=12."""
    return BcryptPasswordHasher()


def test_hash_then_verify_returns_true(hasher: BcryptPasswordHasher) -> None:
    plain = "correct horse battery staple"
    hashed = hasher.hash(plain)
    assert hasher.verify(plain, hashed) is True


def test_verify_wrong_password_returns_false(hasher: BcryptPasswordHasher) -> None:
    hashed = hasher.hash("real-password")
    assert hasher.verify("wrong-password", hashed) is False


def test_verify_broken_hash_returns_false(hasher: BcryptPasswordHasher) -> None:
    """Битый bcrypt-hash не должен крашить процесс auth."""
    assert hasher.verify("any", "not-a-bcrypt-hash") is False


def test_verify_empty_strings_returns_false(hasher: BcryptPasswordHasher) -> None:
    """Пустой пароль или пустой hash — никогда не валидно."""
    assert hasher.verify("", hasher.hash("x")) is False
    assert hasher.verify("x", "") is False


def test_hash_produces_different_outputs_for_same_input(
    hasher: BcryptPasswordHasher,
) -> None:
    """gensalt() даёт уникальную соль на каждом hash'е."""
    a = hasher.hash("same")
    b = hasher.hash("same")
    assert a != b
    # Но оба hash'а должны верифицироваться против исходного пароля.
    assert hasher.verify("same", a) is True
    assert hasher.verify("same", b) is True


def test_work_factor_below_owasp_minimum_rejected() -> None:
    """work_factor < 10 — нарушение OWASP, должен падать сразу при init."""
    with pytest.raises(ValueError, match="work_factor"):
        BcryptPasswordHasher(work_factor=8)


def test_hash_returns_str_not_bytes(hasher: BcryptPasswordHasher) -> None:
    """Хеш — строка (utf-8), пригодная для ORM-поля String(255)."""
    h = hasher.hash("x")
    assert isinstance(h, str)
    assert len(h) == 60  # bcrypt всегда 60 символов


def test_hash_rejects_non_string_input(hasher: BcryptPasswordHasher) -> None:
    with pytest.raises(TypeError):
        hasher.hash(b"bytes-not-allowed")  # type: ignore[arg-type]
