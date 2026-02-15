from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class Credential:
    """Badge/certificate definition — maps to Open Badges v3 Achievement."""

    id: UUID
    type: str  # certificate|badge|microcredential
    name: str
    issuer: str
    version: int = 1

    @staticmethod
    def new(*, type: str, name: str, issuer: str) -> Credential:
        return Credential(id=uuid4(), type=type, name=name, issuer=issuer)


@dataclass(frozen=True, slots=True)
class UserCredential:
    """Issued credential instance — maps to Open Badges v3 AchievementCredential."""

    id: UUID
    user_id: UUID
    credential_id: UUID
    issued_at: int
    status: str = "issued"  # issued|revoked|expired
    evidence_json: str | None = None

    @staticmethod
    def new(
        *,
        user_id: UUID,
        credential_id: UUID,
        issued_at: int,
        evidence_json: str | None = None,
    ) -> UserCredential:
        return UserCredential(
            id=uuid4(),
            user_id=user_id,
            credential_id=credential_id,
            issued_at=issued_at,
            evidence_json=evidence_json,
        )
