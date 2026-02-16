"""add name to users

Revision ID: f04636a50ca2
Revises: a84ce95b74fa
Create Date: 2026-02-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f04636a50ca2"
down_revision: str | Sequence[str] | None = "a84ce95b74fa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("name", sa.String(length=255), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("users", "name")
