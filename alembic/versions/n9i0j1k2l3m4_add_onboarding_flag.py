"""Add has_completed_onboarding to users

Revision ID: n9i0j1k2l3m4
Revises: m8h9i0j1k2l3
Create Date: 2026-03-10 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'n9i0j1k2l3m4'
down_revision: Union[str, None] = 'm8h9i0j1k2l3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('has_completed_onboarding', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'has_completed_onboarding')
