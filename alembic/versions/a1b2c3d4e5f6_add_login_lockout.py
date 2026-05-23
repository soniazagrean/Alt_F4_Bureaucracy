"""add login lockout fields to users

Revision ID: a1b2c3d4e5f6
Revises: f0c4a6d2b7e9
Create Date: 2026-05-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9f3b2a1c7d44'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'failed_login_attempts',
        sa.Integer(),
        nullable=False,
        server_default='0',
    ))
    op.add_column('users', sa.Column(
        'locked_until',
        sa.DateTime(),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
