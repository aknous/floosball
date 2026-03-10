"""Add roster swaps table and swaps_available column

Revision ID: i4d5e6f7g8h9
Revises: h3c4d5e6f7g8
Create Date: 2026-03-07 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i4d5e6f7g8h9'
down_revision: Union[str, None] = 'h3c4d5e6f7g8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add swaps_available column to fantasy_rosters
    op.add_column('fantasy_rosters', sa.Column('swaps_available', sa.Integer(), nullable=False, server_default=sa.text('0')))

    # Create fantasy_roster_swaps table
    op.create_table(
        'fantasy_roster_swaps',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('roster_id', sa.Integer(), nullable=False),
        sa.Column('slot', sa.String(10), nullable=False),
        sa.Column('old_player_id', sa.Integer(), nullable=False),
        sa.Column('new_player_id', sa.Integer(), nullable=False),
        sa.Column('swap_week', sa.Integer(), nullable=False),
        sa.Column('banked_fp', sa.Float(), nullable=False, server_default=sa.text('0.0')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['roster_id'], ['fantasy_rosters.id']),
        sa.ForeignKeyConstraint(['old_player_id'], ['players.id']),
        sa.ForeignKeyConstraint(['new_player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_fantasy_swap_roster', 'fantasy_roster_swaps', ['roster_id'])


def downgrade() -> None:
    op.drop_index('idx_fantasy_swap_roster', 'fantasy_roster_swaps')
    op.drop_table('fantasy_roster_swaps')
    op.drop_column('fantasy_rosters', 'swaps_available')
