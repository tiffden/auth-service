"""PostgreSQL implementation of OAuthClientRepo."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tables import OAuthClientRow
from app.models.oauth_client import OAuthClient


class PgOAuthClientRepo:
    """Satisfies the OAuthClientRepo Protocol using PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, client_id: str) -> OAuthClient | None:
        stmt = select(OAuthClientRow).where(OAuthClientRow.client_id == client_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _row_to_client(row)

    async def register(self, client: OAuthClient) -> None:
        row = OAuthClientRow(
            id=client.id,
            client_id=client.client_id,
            redirect_uris=list(client.redirect_uris),
            is_public=client.is_public,
            allowed_scopes=list(client.allowed_scopes),
        )
        self._session.add(row)
        await self._session.flush()


def _row_to_client(row: OAuthClientRow) -> OAuthClient:
    return OAuthClient(
        id=row.id,
        client_id=row.client_id,
        redirect_uris=tuple(row.redirect_uris) if row.redirect_uris else (),
        is_public=row.is_public,
        allowed_scopes=(
            frozenset(row.allowed_scopes) if row.allowed_scopes else frozenset()
        ),
    )
