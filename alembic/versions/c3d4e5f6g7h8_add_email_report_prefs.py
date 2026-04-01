"""Add email_day_report and email_season_report preference columns to users

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-03-31

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('email_day_report', sa.Boolean(), server_default='1', nullable=False))
    op.add_column('users', sa.Column('email_season_report', sa.Boolean(), server_default='1', nullable=False))


def downgrade():
    op.drop_column('users', 'email_season_report')
    op.drop_column('users', 'email_day_report')
