from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    password_hash: str
    roles: tuple[str, ...] = ()  # immutable
    is_active: bool = True

    @staticmethod
    def new(*, email: str, password_hash: str, roles: tuple[str, ...] = ()) -> User:
        # Keep creation centralized so later you can normalize email,
        # enforce invariants, etc.
        return User(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            roles=roles,
            is_active=True,
        )
