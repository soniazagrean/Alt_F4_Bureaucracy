"""add invoice_number column to documents

Revision ID: 9f3b2a1c7d44
Revises: f0c4a6d2b7e9
Create Date: 2026-04-27 21:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f3b2a1c7d44"
down_revision: Union[str, None] = "f0c4a6d2b7e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("invoice_number", sa.String(length=255), nullable=True))
    op.create_index("ix_documents_invoice_number", "documents", ["invoice_number"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_invoice_number", table_name="documents")
    op.drop_column("documents", "invoice_number")
