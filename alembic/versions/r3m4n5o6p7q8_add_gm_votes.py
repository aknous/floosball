"""Add GM Mode tables (gm_votes, gm_vote_results, gm_fa_ballots)

Revision ID: r3m4n5o6p7q8
Revises: q2l3m4n5o6p7
Create Date: 2026-03-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'r3m4n5o6p7q8'
down_revision: Union[str, None] = 'q2l3m4n5o6p7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # gm_votes table
    op.create_table(
        'gm_votes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('vote_type', sa.String(20), nullable=False),
        sa.Column('target_player_id', sa.Integer(), sa.ForeignKey('players.id'), nullable=True),
        sa.Column('cost_paid', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_gm_votes_team_season', 'gm_votes', ['team_id', 'season'])
    op.create_index('idx_gm_votes_user_season', 'gm_votes', ['user_id', 'season'])

    # gm_vote_results table
    op.create_table(
        'gm_vote_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('vote_type', sa.String(20), nullable=False),
        sa.Column('target_player_id', sa.Integer(), sa.ForeignKey('players.id'), nullable=True),
        sa.Column('total_votes', sa.Integer(), nullable=False),
        sa.Column('threshold', sa.Integer(), nullable=False),
        sa.Column('success_probability', sa.Float(), nullable=False),
        sa.Column('outcome', sa.String(20), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_gm_vote_results_team_season', 'gm_vote_results', ['team_id', 'season'])

    # gm_fa_ballots table
    op.create_table(
        'gm_fa_ballots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('rankings', sa.Text(), nullable=False),
        sa.Column('cost_paid', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'team_id', 'season', name='uq_gm_fa_ballot'),
    )
    op.create_index('idx_gm_fa_ballots_team_season', 'gm_fa_ballots', ['team_id', 'season'])


def downgrade() -> None:
    op.drop_index('idx_gm_fa_ballots_team_season', 'gm_fa_ballots')
    op.drop_table('gm_fa_ballots')
    op.drop_index('idx_gm_vote_results_team_season', 'gm_vote_results')
    op.drop_table('gm_vote_results')
    op.drop_index('idx_gm_votes_user_season', 'gm_votes')
    op.drop_index('idx_gm_votes_team_season', 'gm_votes')
    op.drop_table('gm_votes')
