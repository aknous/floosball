"""Add weekly_card_bonuses table

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g2b3c4d5e6f7'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'weekly_card_bonuses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('roster_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('bonus_fp', sa.Float(), nullable=False, server_default=sa.text('0.0')),
        sa.ForeignKeyConstraint(['roster_id'], ['fantasy_rosters.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('roster_id', 'week', name='uq_weekly_card_bonus_roster_week'),
    )
    op.create_index('idx_weekly_card_bonus_season_week', 'weekly_card_bonuses', ['season', 'week'])


def downgrade() -> None:
    op.drop_index('idx_weekly_card_bonus_season_week', 'weekly_card_bonuses')
    op.drop_table('weekly_card_bonuses')
