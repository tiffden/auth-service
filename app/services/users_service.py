from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    email: str


_FAKE_USERS: list[User] = [
    User(id=1, email="tee@example.com"),
    User(id=2, email="d-man@example.com"),
]


def list_users() -> list[User]:
    return list(_FAKE_USERS)


class UserValidationError(ValueError):
    pass


class UserAlreadyExistsError(Exception):
    pass


def create_user(email: str) -> User:
    email = email.strip().lower()
    if not email:
        raise UserValidationError("email must be non-empty")

    if any(u.email == email for u in _FAKE_USERS):
        raise UserAlreadyExistsError(email)

    next_id = max((u.id for u in _FAKE_USERS), default=0) + 1
    user = User(id=next_id, email=email)
    _FAKE_USERS.append(user)
    return user
