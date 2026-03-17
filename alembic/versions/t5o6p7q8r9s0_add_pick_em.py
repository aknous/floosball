"""Add pick_em_picks table for Prognostications minigame

Revision ID: t5o6p7q8r9s0
Revises: s4n5o6p7q8r9
Create Date: 2026-03-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 't5o6p7q8r9s0'
down_revision: Union[str, None] = 's4n5o6p7q8r9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pick_em_picks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('game_index', sa.Integer(), nullable=False),
        sa.Column('home_team_id', sa.Integer(), nullable=False),
        sa.Column('away_team_id', sa.Integer(), nullable=False),
        sa.Column('picked_team_id', sa.Integer(), nullable=False),
        sa.Column('correct', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'season', 'week', 'game_index', name='uq_pickem_pick'),
    )
    op.create_index('idx_pickem_user_season', 'pick_em_picks', ['user_id', 'season'])
    op.create_index('idx_pickem_season_week', 'pick_em_picks', ['season', 'week'])


def downgrade() -> None:
    op.drop_index('idx_pickem_season_week', table_name='pick_em_picks')
    op.drop_index('idx_pickem_user_season', table_name='pick_em_picks')
    op.drop_table('pick_em_picks')
