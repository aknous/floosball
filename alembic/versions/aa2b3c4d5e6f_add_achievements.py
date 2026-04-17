"""Add achievements, user_achievements, and pending_rewards tables

Revision ID: aa2b3c4d5e6f
Revises: z1a2b3c4d5e6
Create Date: 2026-04-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'aa2b3c4d5e6f'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'achievements',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('key', sa.String(50), nullable=False, unique=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(300), nullable=False),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('scope', sa.String(20), nullable=False, server_default='once'),
        sa.Column('target', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('reward_config', sa.JSON(), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'user_achievements',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('achievement_id', sa.Integer(), sa.ForeignKey('achievements.id'), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'achievement_id', 'season', name='uq_user_achievement_season'),
    )
    op.create_index('idx_user_achievements_user', 'user_achievements', ['user_id'])
    op.create_index('idx_user_achievements_achievement', 'user_achievements', ['achievement_id'])

    op.create_table(
        'pending_rewards',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('slug', sa.String(30), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('available_at', sa.DateTime(), nullable=False),
        sa.Column('defer_until_season', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
    )
    op.create_index('idx_pending_rewards_user_claimed', 'pending_rewards', ['user_id', 'claimed_at'])


def downgrade():
    op.drop_index('idx_pending_rewards_user_claimed', table_name='pending_rewards')
    op.drop_table('pending_rewards')
    op.drop_index('idx_user_achievements_achievement', table_name='user_achievements')
    op.drop_index('idx_user_achievements_user', table_name='user_achievements')
    op.drop_table('user_achievements')
    op.drop_table('achievements')
