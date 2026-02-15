from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class Organization:
    id: UUID
    name: str
    slug: str
    plan: str = "free"  # free|team|enterprise
    status: str = "active"  # active|suspended

    @staticmethod
    def new(*, name: str, slug: str, plan: str = "free") -> Organization:
        return Organization(id=uuid4(), name=name, slug=slug, plan=plan)


@dataclass(frozen=True, slots=True)
class OrgMembership:
    org_id: UUID
    user_id: UUID
    org_role: str  # owner|admin|instructor|learner
