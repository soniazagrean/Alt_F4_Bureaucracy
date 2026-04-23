"""add audit action values

Revision ID: e3b2a7c4d9f1
Revises: d247f5e9c1ba
Create Date: 2026-04-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e3b2a7c4d9f1"
down_revision: Union[str, None] = "d247f5e9c1ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE auditactionenum ADD VALUE IF NOT EXISTS 'INSPECT'")
    op.execute("ALTER TYPE auditactionenum ADD VALUE IF NOT EXISTS 'APPROVE'")
    op.execute("ALTER TYPE auditactionenum ADD VALUE IF NOT EXISTS 'MANUAL_EDIT'")


def downgrade() -> None:
    # Enum value removal is not supported safely in PostgreSQL.
    pass
