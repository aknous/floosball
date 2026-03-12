"""Add shop power-ups tables, purchased_swaps, and featured shop refresh columns

Revision ID: q2l3m4n5o6p7
Revises: p1k2l3m4n5o6
Create Date: 2026-03-10 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'q2l3m4n5o6p7'
down_revision: Union[str, None] = 'p1k2l3m4n5o6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ShopPurchase table
    op.create_table(
        'shop_purchases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('item_slug', sa.String(30), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('price_paid', sa.Integer(), nullable=False),
        sa.Column('expires_at_week', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_shop_purchase_user_season', 'shop_purchases', ['user_id', 'season'])
    op.create_index('idx_shop_purchase_item_week', 'shop_purchases', ['item_slug', 'user_id', 'season', 'week'])

    # UserModifierOverride table
    op.create_table(
        'user_modifier_overrides',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('override_modifier', sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'season', 'week', name='uq_mod_override_user_week'),
    )
    op.create_index('idx_mod_override_user_season_week', 'user_modifier_overrides', ['user_id', 'season', 'week'])

    # Add purchased_swaps to fantasy_rosters
    op.add_column('fantasy_rosters', sa.Column('purchased_swaps', sa.Integer(), server_default='0', nullable=False))

    # Add generated_at columns to featured_shop_cards
    op.add_column('featured_shop_cards', sa.Column('generated_at', sa.DateTime(), nullable=True))
    op.add_column('featured_shop_cards', sa.Column('generated_at_week', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('featured_shop_cards', 'generated_at_week')
    op.drop_column('featured_shop_cards', 'generated_at')
    op.drop_column('fantasy_rosters', 'purchased_swaps')
    op.drop_index('idx_mod_override_user_season_week', 'user_modifier_overrides')
    op.drop_table('user_modifier_overrides')
    op.drop_index('idx_shop_purchase_item_week', 'shop_purchases')
    op.drop_index('idx_shop_purchase_user_season', 'shop_purchases')
    op.drop_table('shop_purchases')
