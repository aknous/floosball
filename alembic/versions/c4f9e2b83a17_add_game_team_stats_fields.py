"""Add game team stats fields

Revision ID: c4f9e2b83a17
Revises: 5b3a86eac3dd
Create Date: 2026-03-03 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f9e2b83a17'
down_revision: Union[str, Sequence[str], None] = '5b3a86eac3dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    'home_rush_yards', 'home_pass_yards', 'home_rush_tds', 'home_pass_tds',
    'home_fgs', 'home_sacks', 'home_ints', 'home_fum_rec',
    'away_rush_yards', 'away_pass_yards', 'away_rush_tds', 'away_pass_tds',
    'away_fgs', 'away_sacks', 'away_ints', 'away_fum_rec',
]


def upgrade() -> None:
    """Add team-level game stat columns for accurate resume averages."""
    for col in _COLUMNS:
        op.add_column('games', sa.Column(col, sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove team-level game stat columns."""
    for col in reversed(_COLUMNS):
        op.drop_column('games', col)
