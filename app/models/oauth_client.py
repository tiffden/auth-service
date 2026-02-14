from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class OAuthClient:
    id: UUID
    client_id: str
    redirect_uris: tuple[str, ...]
    is_public: bool
    allowed_scopes: frozenset[str]

    @staticmethod
    def new(
        *,
        client_id: str,
        redirect_uris: tuple[str, ...],
        is_public: bool,
        allowed_scopes: frozenset[str],
    ) -> OAuthClient:
        # Keep creation centralized so later you can normalize email,
        # enforce invariants, etc.
        return OAuthClient(
            id=uuid4(),
            client_id=client_id,
            redirect_uris=redirect_uris,
            is_public=is_public,
            allowed_scopes=frozenset(allowed_scopes),
        )
