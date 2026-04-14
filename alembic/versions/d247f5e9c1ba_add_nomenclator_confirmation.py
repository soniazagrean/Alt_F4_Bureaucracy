"""add nomenclator confirmation fields for NV-025

Revision ID: d247f5e9c1ba
Revises: c183b94ea2f1
Create Date: 2026-04-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd247f5e9c1ba'
down_revision = 'c183b94ea2f1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nomenclator confirmation fields for NV-025
    op.add_column('documents', sa.Column('nomenclator_confirmed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('documents', sa.Column('nomenclator_confirmed_at', sa.DateTime(), nullable=True))
    
    # Remove server default for clean ORM defaults
    op.alter_column('documents', 'nomenclator_confirmed', server_default=None)


def downgrade() -> None:
    op.drop_column('documents', 'nomenclator_confirmed_at')
    op.drop_column('documents', 'nomenclator_confirmed')
