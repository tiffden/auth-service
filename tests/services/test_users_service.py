from __future__ import annotations

import pytest

from app.services import users_service


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
