"""Add featured_shop_cards table

Revision ID: e8f9a0b1c2d3
Revises: d7f8a9b0c1e2
Create Date: 2026-03-05 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, None] = 'd7f8a9b0c1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'featured_shop_cards',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('card_template_id', sa.Integer(), sa.ForeignKey('card_templates.id'), nullable=False),
        sa.Column('purchased', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_featured_shop_user_season', 'featured_shop_cards', ['user_id', 'season'])


def downgrade() -> None:
    op.drop_index('idx_featured_shop_user_season', table_name='featured_shop_cards')
    op.drop_table('featured_shop_cards')
