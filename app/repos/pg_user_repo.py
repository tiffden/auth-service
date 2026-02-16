"""PostgreSQL implementation of UserRepo."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tables import UserRow
from app.models.user import User


class PgUserRepo:
    """Satisfies the UserRepo Protocol using PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(UserRow).where(UserRow.id == user_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _row_to_user(row)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserRow).where(UserRow.email == email)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _row_to_user(row)

    async def add(self, user: User) -> None:
        row = UserRow(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            name=user.name,
            roles=list(user.roles),
            is_active=user.is_active,
        )
        self._session.add(row)
        await self._session.flush()

    async def set_active(self, user_id: UUID, is_active: bool) -> None:
        stmt = update(UserRow).where(UserRow.id == user_id).values(is_active=is_active)
        await self._session.execute(stmt)

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        stmt = (
            update(UserRow)
            .where(UserRow.id == user_id)
            .values(password_hash=password_hash)
        )
        await self._session.execute(stmt)

    async def update_name(self, user_id: UUID, name: str) -> User | None:
        stmt = update(UserRow).where(UserRow.id == user_id).values(name=name)
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            return None
        return await self.get_by_id(user_id)


def _row_to_user(row: UserRow) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        name=row.name or "",
        roles=tuple(row.roles) if row.roles else (),
        is_active=row.is_active,
    )
