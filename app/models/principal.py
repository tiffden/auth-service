from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated identity extracted from a validated JWT.

    Carried through the request via FastAPI's dependency system.
    Endpoints receive this instead of a raw username string.

    Platform-level fields (always set):
        user_id: subject from JWT
        roles: platform roles (admin, user)

    Org-level fields (set by resolve_org_principal when request is org-scoped):
        org_id: active organization for this request
        org_role: role within that org (owner|admin|instructor|learner)
    """

    user_id: str
    roles: frozenset[str]
    org_id: UUID | None = None
    org_role: str | None = None

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, roles: set[str]) -> bool:
        return bool(self.roles & roles)

    def has_org_role(self, role: str) -> bool:
        return self.org_role == role

    def has_any_org_role(self, roles: set[str]) -> bool:
        return self.org_role in roles

    def is_platform_admin(self) -> bool:
        return "admin" in self.roles
