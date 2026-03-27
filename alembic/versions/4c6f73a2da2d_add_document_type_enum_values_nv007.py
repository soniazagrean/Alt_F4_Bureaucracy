"""add_document_type_enum_values_nv007

Revision ID: 4c6f73a2da2d
Revises: 2b4e32947dfb
Create Date: 2026-03-27 08:31:18.378566

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c6f73a2da2d'
down_revision: Union[str, None] = '2b4e32947dfb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE documenttypeenum ADD VALUE IF NOT EXISTS 'adresa'")
    op.execute("ALTER TYPE documenttypeenum ADD VALUE IF NOT EXISTS 'cerere'")
    op.execute("ALTER TYPE documenttypeenum ADD VALUE IF NOT EXISTS 'hcl'")
    op.execute("ALTER TYPE documenttypeenum ADD VALUE IF NOT EXISTS 'deviz'")

def downgrade() -> None:
    # PostgreSQL does not support removing enum values natively.
    pass