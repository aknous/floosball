"""Add player defensive rating columns

Revision ID: a1b2c3d4e5f6
Revises: z1a2b3c4d5e6
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('players') as batch_op:
        batch_op.add_column(sa.Column('offensive_rating', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('defensive_rating', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('defensive_position', sa.String(5), nullable=True))


def downgrade():
    with op.batch_alter_table('players') as batch_op:
        batch_op.drop_column('defensive_position')
        batch_op.drop_column('defensive_rating')
        batch_op.drop_column('offensive_rating')
