"""add review statuses to document status enum

Revision ID: f0c4a6d2b7e9
Revises: e3b2a7c4d9f1
Create Date: 2026-04-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f0c4a6d2b7e9"
down_revision: Union[str, None] = "e3b2a7c4d9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE documentstatusenum ADD VALUE IF NOT EXISTS 'REVIEW'")
    op.execute("ALTER TYPE documentstatusenum ADD VALUE IF NOT EXISTS 'APPROVED'")
    op.execute("ALTER TYPE documentstatusenum ADD VALUE IF NOT EXISTS 'RETURNED'")


def downgrade() -> None:
    # Enum value removal is not supported safely in PostgreSQL.
    pass
