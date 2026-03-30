"""Add mvp_player_id and all_pro_player_ids columns to seasons table

Revision ID: b2c3d4e5f6g7
Revises: z1a2b3c4d5e6
Create Date: 2026-03-29

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'b2c3d4e5f6g7'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('seasons', sa.Column('mvp_player_id', sa.Integer(), sa.ForeignKey('players.id'), nullable=True))
    op.add_column('seasons', sa.Column('all_pro_player_ids', sa.String(), nullable=True))


def downgrade():
    op.drop_column('seasons', 'all_pro_player_ids')
    op.drop_column('seasons', 'mvp_player_id')
