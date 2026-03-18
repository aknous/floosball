"""Add points columns to pick_em_picks

Revision ID: v7w8x9y0z1a2
Revises: u6p7q8r9s0t1
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'v7w8x9y0z1a2'
down_revision = 'u6p7q8r9s0t1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('pick_em_picks', sa.Column('points_multiplier', sa.Float(), nullable=True))
    op.add_column('pick_em_picks', sa.Column('points_earned', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('pick_em_picks', 'points_earned')
    op.drop_column('pick_em_picks', 'points_multiplier')
