"""Add email_opt_out to users

Revision ID: o0j1k2l3m4n5
Revises: n9i0j1k2l3m4
Create Date: 2026-03-10 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'o0j1k2l3m4n5'
down_revision: Union[str, None] = 'n9i0j1k2l3m4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email_opt_out', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'email_opt_out')
