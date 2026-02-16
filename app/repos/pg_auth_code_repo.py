"""PostgreSQL implementation of AuthCodeRepo."""

from __future__ import annotations

import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tables import AuthorizationCodeRow
from app.models.authorization_code import AuthorizationCode


class PgAuthCodeRepo:
    """Satisfies the AuthCodeRepo Protocol using PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, record: AuthorizationCode) -> None:
        row = AuthorizationCodeRow(
            id=record.id,
            code_hash=record.code_hash,
            client_id=record.client_id,
            redirect_uri=record.redirect_uri,
            scope=record.scope,
            code_challenge=record.code_challenge,
            code_challenge_method=record.code_challenge_method,
            user_id=record.user_id,
            expires_at=record.expires_at,
            used_at=record.used_at,
        )
        self._session.add(row)
        await self._session.flush()

    async def get_by_code_hash(self, code_hash: str) -> AuthorizationCode | None:
        stmt = select(AuthorizationCodeRow).where(
            AuthorizationCodeRow.code_hash == code_hash
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _row_to_auth_code(row)

    async def mark_used(self, code_hash: str) -> AuthorizationCode | None:
        """Atomically mark a code as used. Returns the updated record, or None
        if the code doesn't exist or was already consumed."""
        stmt = select(AuthorizationCodeRow).where(
            AuthorizationCodeRow.code_hash == code_hash
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        if row.used_at is not None:
            return None

        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        update_stmt = (
            update(AuthorizationCodeRow)
            .where(AuthorizationCodeRow.code_hash == code_hash)
            .where(AuthorizationCodeRow.used_at.is_(None))
            .values(used_at=now)
        )
        result = await self._session.execute(update_stmt)
        if result.rowcount == 0:
            return None  # concurrent update won the race

        row.used_at = now
        return _row_to_auth_code(row)


def _row_to_auth_code(row: AuthorizationCodeRow) -> AuthorizationCode:
    return AuthorizationCode(
        id=row.id,
        code_hash=row.code_hash,
        client_id=row.client_id,
        redirect_uri=row.redirect_uri,
        scope=row.scope,
        code_challenge=row.code_challenge,
        code_challenge_method=row.code_challenge_method,
        user_id=row.user_id,
        expires_at=row.expires_at,
        used_at=row.used_at,
    )
