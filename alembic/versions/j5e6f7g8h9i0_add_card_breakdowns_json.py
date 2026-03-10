"""Add breakdowns_json to weekly_card_bonuses

Revision ID: j5e6f7g8h9i0
Revises: i4d5e6f7g8h9
Create Date: 2026-03-07 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j5e6f7g8h9i0'
down_revision: Union[str, None] = 'i4d5e6f7g8h9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('weekly_card_bonuses', sa.Column('breakdowns_json', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('weekly_card_bonuses', 'breakdowns_json')
