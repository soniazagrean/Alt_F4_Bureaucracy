"""add retry and error metadata to documents

Revision ID: bf8f1c9e2a7c
Revises: a1c4e6263032
Create Date: 2026-04-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'bf8f1c9e2a7c'
down_revision = 'a1c4e6263032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum label for error state
    op.execute("ALTER TYPE documentstatusenum ADD VALUE IF NOT EXISTS 'ERROR'")

    # Add retry metadata fields
    op.add_column('documents', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('documents', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('error_timestamp', sa.DateTime(), nullable=True))

    # Remove server default for clean ORM defaults
    op.alter_column('documents', 'retry_count', server_default=None)


def downgrade() -> None:
    op.drop_column('documents', 'error_timestamp')
    op.drop_column('documents', 'error_message')
    op.drop_column('documents', 'retry_count')
    # The enum label is kept because PostgreSQL does not support safe removal of enum values.
