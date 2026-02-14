from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated identity extracted from a validated JWT.

    Carried through the request via FastAPI's dependency system.
    Endpoints receive this instead of a raw username string.
    """

    user_id: str
    roles: frozenset[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, roles: set[str]) -> bool:
        return bool(self.roles & roles)
