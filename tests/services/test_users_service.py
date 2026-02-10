from __future__ import annotations

import pytest

from app.services import users_service
from app.services.users_service import User


def test_list_users_returns_seed_users() -> None:
    users = users_service.list_users()
    assert [u.id for u in users] == [1, 2]
    assert [u.email for u in users] == ["tee@example.com", "d-man@example.com"]


def test_create_user_adds_new_user_with_next_id() -> None:
    user = users_service.create_user("third@example.com")
    assert user.id == 3
    assert user.email == "third@example.com"

    users = users_service.list_users()
    assert users[-1].email == "third@example.com"


def test_create_user_rejects_duplicate_email() -> None:
    users_service.create_user("dupe@example.com")

    with pytest.raises(users_service.UserAlreadyExistsError):
        users_service.create_user("dupe@example.com")


def test_create_user_rejects_blank_email() -> None:
    with pytest.raises(users_service.UserValidationError):
        users_service.create_user("   ")


# ---- email normalization ----


def test_create_user_lowercases_email() -> None:
    user = users_service.create_user("LOUD@EXAMPLE.COM")
    assert user.email == "loud@example.com"


def test_create_user_strips_whitespace_from_email() -> None:
    user = users_service.create_user("  padded@example.com  ")
    assert user.email == "padded@example.com"


def test_create_user_rejects_empty_string() -> None:
    with pytest.raises(users_service.UserValidationError, match="non-empty"):
        users_service.create_user("")


# ---- duplicate detection edge cases ----


def test_create_user_rejects_duplicate_of_seed_user() -> None:
    with pytest.raises(users_service.UserAlreadyExistsError):
        users_service.create_user("tee@example.com")


def test_create_user_rejects_case_variant_duplicate() -> None:
    users_service.create_user("unique@example.com")
    with pytest.raises(users_service.UserAlreadyExistsError):
        users_service.create_user("UNIQUE@EXAMPLE.COM")


# ---- ID assignment ----


def test_create_user_ids_increment_sequentially() -> None:
    u3 = users_service.create_user("a@example.com")
    u4 = users_service.create_user("b@example.com")
    u5 = users_service.create_user("c@example.com")
    assert (u3.id, u4.id, u5.id) == (3, 4, 5)


def test_create_user_assigns_id_1_when_list_is_empty() -> None:
    users_service._FAKE_USERS.clear()
    user = users_service.create_user("first@example.com")
    assert user.id == 1


# ---- list_users isolation ----


def test_list_users_returns_copy_not_internal_list() -> None:
    returned = users_service.list_users()
    returned.clear()
    assert len(users_service.list_users()) == 2


# ---- User dataclass ----


def test_user_dataclass_is_frozen() -> None:
    user = User(id=1, email="frozen@example.com")
    with pytest.raises(AttributeError):
        user.email = "mutated@example.com"  # type: ignore[misc]
