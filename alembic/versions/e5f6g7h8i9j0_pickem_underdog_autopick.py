"""Add underdog_multiplier to pick_em_picks, auto_pick_favorites to users

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'e5f6g7h8i9j0'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pick_em_picks', sa.Column('underdog_multiplier', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('auto_pick_favorites', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    op.drop_column('users', 'auto_pick_favorites')
    op.drop_column('pick_em_picks', 'underdog_multiplier')
