"""Add defensive_talent modifier to player_attributes

Revision ID: a1b2c3d4e5f6
Revises: z1a2b3c4d5e6
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('player_attributes', sa.Column('defensive_talent', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    op.drop_column('player_attributes', 'defensive_talent')
