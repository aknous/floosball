"""Add favorite team lock and fantasy rosters

Revision ID: a1b2c3d4e5f6
Revises: c4f9e2b83a17
Create Date: 2026-03-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c4f9e2b83a17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add favorite team lock columns and fantasy roster tables."""
    # User model additions
    op.add_column('users', sa.Column('pending_favorite_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True))
    op.add_column('users', sa.Column('favorite_team_locked_season', sa.Integer(), nullable=True))

    # Fantasy rosters table
    op.create_table(
        'fantasy_rosters',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('is_locked', sa.Boolean(), default=False),
        sa.Column('locked_at', sa.DateTime(), nullable=True),
        sa.Column('total_points', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'season', name='uq_fantasy_roster_user_season'),
    )
    op.create_index('idx_fantasy_roster_season', 'fantasy_rosters', ['season'])
    op.create_index('idx_fantasy_roster_user', 'fantasy_rosters', ['user_id'])

    # Fantasy roster players table
    op.create_table(
        'fantasy_roster_players',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('roster_id', sa.Integer(), sa.ForeignKey('fantasy_rosters.id'), nullable=False),
        sa.Column('player_id', sa.Integer(), sa.ForeignKey('players.id'), nullable=False),
        sa.Column('slot', sa.String(10), nullable=False),
        sa.Column('points_at_lock', sa.Float(), default=0.0),
        sa.UniqueConstraint('roster_id', 'slot', name='uq_fantasy_roster_slot'),
    )
    op.create_index('idx_fantasy_player_roster', 'fantasy_roster_players', ['roster_id'])


def downgrade() -> None:
    """Remove fantasy roster tables and favorite team lock columns."""
    op.drop_index('idx_fantasy_player_roster', table_name='fantasy_roster_players')
    op.drop_table('fantasy_roster_players')
    op.drop_index('idx_fantasy_roster_user', table_name='fantasy_rosters')
    op.drop_index('idx_fantasy_roster_season', table_name='fantasy_rosters')
    op.drop_table('fantasy_rosters')
    op.drop_column('users', 'favorite_team_locked_season')
    op.drop_column('users', 'pending_favorite_team_id')
