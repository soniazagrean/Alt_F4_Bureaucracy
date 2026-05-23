"""add TOTP 2FA fields to users

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-05-23 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'totp_secret', sa.String(64), nullable=True,
    ))
    op.add_column('users', sa.Column(
        'totp_enabled', sa.Boolean(), nullable=False, server_default='false',
    ))


def downgrade() -> None:
    op.drop_column('users', 'totp_enabled')
    op.drop_column('users', 'totp_secret')