"""Add reach attribute to player_attributes

Revision ID: x9y0z1a2b3c4
Revises: c4f9e2b83a17
Create Date: 2026-03-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'x9y0z1a2b3c4'
down_revision = 'c4f9e2b83a17'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('player_attributes', sa.Column('reach', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('player_attributes', sa.Column('potential_reach', sa.Integer(), nullable=True, server_default='0'))

    # Existing players get reach=0; playerManager backfills with randomized values at load time


def downgrade() -> None:
    op.drop_column('player_attributes', 'potential_reach')
    op.drop_column('player_attributes', 'reach')
