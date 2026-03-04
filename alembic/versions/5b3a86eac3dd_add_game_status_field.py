"""Add game status field

Revision ID: 5b3a86eac3dd
Revises: 818e7a7bffc0
Create Date: 2026-03-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b3a86eac3dd'
down_revision: Union[str, Sequence[str], None] = '818e7a7bffc0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing rows are completed games, so default them to 'final'.
    # New scheduled-game rows will be inserted with status='scheduled' explicitly.
    op.add_column('games', sa.Column('status', sa.String(20), server_default='final', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('games', 'status')
