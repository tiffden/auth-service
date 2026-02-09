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
