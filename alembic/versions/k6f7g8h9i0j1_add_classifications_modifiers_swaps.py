"""Add classifications, weekly modifiers, and swap tracking fields

Revision ID: k6f7g8h9i0j1
Revises: j5e6f7g8h9i0
Create Date: 2026-03-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k6f7g8h9i0j1'
down_revision: Union[str, None] = 'j5e6f7g8h9i0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Classification on card templates
    op.add_column('card_templates', sa.Column('classification', sa.String(30), nullable=True))

    # Auto-fill roster preference on users
    op.add_column('users', sa.Column('auto_fill_roster', sa.Boolean(), nullable=False, server_default=sa.text('1')))

    # All-Pro swap bonus exhaustion tracking on user cards
    op.add_column('user_cards', sa.Column('last_swap_grant_cycle', sa.Integer(), nullable=False, server_default=sa.text('0')))

    # All-Pro swap bonus active flag on equipped cards
    op.add_column('equipped_cards', sa.Column('swap_bonus_active', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    # Weekly modifiers table
    op.create_table(
        'weekly_modifiers',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('modifier', sa.String(20), nullable=False),
        sa.UniqueConstraint('season', 'week', name='uq_weekly_modifier_season_week'),
    )


def downgrade() -> None:
    op.drop_table('weekly_modifiers')
    op.drop_column('equipped_cards', 'swap_bonus_active')
    op.drop_column('user_cards', 'last_swap_grant_cycle')
    op.drop_column('users', 'auto_fill_roster')
    op.drop_column('card_templates', 'classification')
