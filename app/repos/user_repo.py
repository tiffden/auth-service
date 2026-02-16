from __future__ import annotations

from dataclasses import replace
from typing import Protocol
from uuid import UUID

from app.models.user import User


class UserRepo(Protocol):
    def get_by_id(self, user_id: UUID) -> User | None: ...
    def get_by_email(self, email: str) -> User | None: ...
    def add(self, user: User) -> None: ...
    def set_active(self, user_id: UUID, is_active: bool) -> None: ...
    def update_password_hash(self, user_id: UUID, password_hash: str) -> None: ...
    def update_name(self, user_id: UUID, name: str) -> User | None: ...


class InMemoryUserRepo:
    def __init__(self) -> None:
        self._by_email: dict[str, User] = {}
        self._by_id: dict[UUID, User] = {}

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        # (TODO: lowercase/strip here or upstream)
        return self._by_email.get(email)

    def add(self, user: User) -> None:
        # Minimal constraints; later you’ll enforce uniqueness at DB level too.
        if user.email in self._by_email:
            raise ValueError("email already exists")
        self._by_email[user.email] = user
        self._by_id[user.id] = user

    def set_active(self, user_id: UUID, is_active: bool) -> None:
        u = self._by_id.get(user_id)
        if u is None:
            raise KeyError("user not found")

        updated = replace(u, is_active=is_active)
        self._by_id[user_id] = updated
        self._by_email[updated.email] = updated

    def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        u = self._by_id.get(user_id)
        if u is None:
            raise KeyError("user not found")

        updated = replace(u, password_hash=password_hash)
        self._by_id[user_id] = updated
        self._by_email[updated.email] = updated

    def update_name(self, user_id: UUID, name: str) -> User | None:
        u = self._by_id.get(user_id)
        if u is None:
            return None

        updated = replace(u, name=name)
        self._by_id[user_id] = updated
        self._by_email[updated.email] = updated
        return updated
