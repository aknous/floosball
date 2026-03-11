"""Add stats_at_lock to fantasy_roster_players

Revision ID: p1k2l3m4n5o6
Revises: o0j1k2l3m4n5
Create Date: 2026-03-10 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'p1k2l3m4n5o6'
down_revision: Union[str, None] = 'o0j1k2l3m4n5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fantasy_roster_players',
        sa.Column('stats_at_lock', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('fantasy_roster_players', 'stats_at_lock')
