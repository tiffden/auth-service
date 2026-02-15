from __future__ import annotations

from dataclasses import replace
from typing import Protocol
from uuid import UUID

from app.models.organization import OrgMembership


class OrgMembershipRepo(Protocol):
    def get(self, org_id: UUID, user_id: UUID) -> OrgMembership | None: ...
    def add(self, membership: OrgMembership) -> None: ...
    def remove(self, org_id: UUID, user_id: UUID) -> bool: ...
    def update_role(
        self, org_id: UUID, user_id: UUID, new_role: str
    ) -> OrgMembership | None: ...
    def list_by_org(self, org_id: UUID) -> list[OrgMembership]: ...
    def list_by_user(self, user_id: UUID) -> list[OrgMembership]: ...


class InMemoryOrgMembershipRepo:
    def __init__(self) -> None:
        self._store: dict[tuple[UUID, UUID], OrgMembership] = {}

    def get(self, org_id: UUID, user_id: UUID) -> OrgMembership | None:
        return self._store.get((org_id, user_id))

    def add(self, membership: OrgMembership) -> None:
        key = (membership.org_id, membership.user_id)
        if key in self._store:
            raise ValueError("membership already exists")
        self._store[key] = membership

    def remove(self, org_id: UUID, user_id: UUID) -> bool:
        return self._store.pop((org_id, user_id), None) is not None

    def update_role(
        self, org_id: UUID, user_id: UUID, new_role: str
    ) -> OrgMembership | None:
        key = (org_id, user_id)
        existing = self._store.get(key)
        if existing is None:
            return None
        updated = replace(existing, org_role=new_role)
        self._store[key] = updated
        return updated

    def list_by_org(self, org_id: UUID) -> list[OrgMembership]:
        return [m for m in self._store.values() if m.org_id == org_id]

    def list_by_user(self, user_id: UUID) -> list[OrgMembership]:
        return [m for m in self._store.values() if m.user_id == user_id]
