from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.models.organization import Organization


class OrgRepo(Protocol):
    def get_by_id(self, org_id: UUID) -> Organization | None: ...
    def get_by_slug(self, slug: str) -> Organization | None: ...
    def add(self, org: Organization) -> None: ...
    def list_all(self) -> list[Organization]: ...


class InMemoryOrgRepo:
    def __init__(self) -> None:
        self._by_id: dict[UUID, Organization] = {}
        self._by_slug: dict[str, Organization] = {}

    def get_by_id(self, org_id: UUID) -> Organization | None:
        return self._by_id.get(org_id)

    def get_by_slug(self, slug: str) -> Organization | None:
        return self._by_slug.get(slug)

    def add(self, org: Organization) -> None:
        if org.slug in self._by_slug:
            raise ValueError("slug already exists")
        self._by_id[org.id] = org
        self._by_slug[org.slug] = org

    def list_all(self) -> list[Organization]:
        return list(self._by_id.values())
