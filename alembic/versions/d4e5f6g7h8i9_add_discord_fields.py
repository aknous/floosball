"""Add discord_id and discord_dm_reminders columns to users

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-04-14

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'd4e5f6g7h8i9'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('discord_id', sa.String(30), nullable=True))
    op.add_column('users', sa.Column('discord_dm_reminders', sa.Boolean(), server_default='0', nullable=False))
    op.create_unique_constraint('uq_users_discord_id', 'users', ['discord_id'])


def downgrade():
    op.drop_constraint('uq_users_discord_id', 'users', type_='unique')
    op.drop_column('users', 'discord_dm_reminders')
    op.drop_column('users', 'discord_id')
