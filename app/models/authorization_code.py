from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

# •	code_hash: str
# •	client_id: str
# •	redirect_uri: str
# •	scope: str (space-delimited)
# •	code_challenge: str
# •	code_challenge_method: Literal["S256"]
# •	user_id: str
# •	expires_at: datetime
# •	used_at: datetime | None


@dataclass(frozen=True, slots=True)
class AuthorizationCode:
    id: UUID
    code_hash: str
    client_id: str
    redirect_uri: str
    scope: str
    code_challenge: str
    code_challenge_method: str
    user_id: str
    expires_at: int
    used_at: int | None

    @staticmethod
    def new(
        *,
        code_hash: str,
        client_id: str,
        redirect_uri: str,
        scope: str,
        code_challenge: str,
        code_challenge_method: str,
        user_id: str,
        expires_at: int,
    ) -> AuthorizationCode:
        return AuthorizationCode(
            id=uuid4(),
            code_hash=code_hash,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            user_id=user_id,
            expires_at=expires_at,
            used_at=None,
        )
