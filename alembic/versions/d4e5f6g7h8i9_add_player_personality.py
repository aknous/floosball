"""Add archetype/quirk columns and personality history table

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'd4e5f6g7h8i9'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade():
    # Add archetype/quirk columns to player_attributes
    with op.batch_alter_table('player_attributes') as batch_op:
        batch_op.add_column(sa.Column('archetype', sa.String(30), nullable=True))
        batch_op.add_column(sa.Column('quirk', sa.String(30), nullable=True))

    # Create personality history table
    op.create_table(
        'player_personality_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('player_id', sa.Integer(), sa.ForeignKey('players.id'), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('change_type', sa.String(20), nullable=False),
        sa.Column('from_value', sa.String(30), nullable=True),
        sa.Column('to_value', sa.String(30), nullable=True),
        sa.Column('reason', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('idx_personality_history_player', 'player_personality_history', ['player_id'])
    op.create_index('idx_personality_history_season', 'player_personality_history', ['season'])


def downgrade():
    op.drop_index('idx_personality_history_season', table_name='player_personality_history')
    op.drop_index('idx_personality_history_player', table_name='player_personality_history')
    op.drop_table('player_personality_history')

    with op.batch_alter_table('player_attributes') as batch_op:
        batch_op.drop_column('quirk')
        batch_op.drop_column('archetype')
