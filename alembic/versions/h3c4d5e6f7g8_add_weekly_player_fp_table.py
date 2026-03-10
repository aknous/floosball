"""Add weekly_player_fp table

Revision ID: h3c4d5e6f7g8
Revises: g2b3c4d5e6f7
Create Date: 2026-03-07 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h3c4d5e6f7g8'
down_revision: Union[str, None] = 'g2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'weekly_player_fp',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('fantasy_points', sa.Float(), nullable=True, server_default=sa.text('0.0')),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'season', 'week', name='uq_weekly_player_fp'),
    )
    op.create_index('idx_weekly_player_fp_season', 'weekly_player_fp', ['season'])


def downgrade() -> None:
    op.drop_index('idx_weekly_player_fp_season', 'weekly_player_fp')
    op.drop_table('weekly_player_fp')
