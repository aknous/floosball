"""Add trading card system tables

Revision ID: d7f8a9b0c1e2
Revises: a1b2c3d4e5f6
Create Date: 2026-03-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7f8a9b0c1e2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trading card system: card_templates, user_cards, equipped_cards,
    user_currency, currency_transactions, pack_types, pack_openings,
    and card_bonus_points column on fantasy_rosters."""

    # card_templates
    op.create_table(
        'card_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.Integer(), sa.ForeignKey('players.id'), nullable=False),
        sa.Column('edition', sa.String(20), nullable=False),
        sa.Column('season_created', sa.Integer(), nullable=False),
        sa.Column('is_rookie', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('player_name', sa.String(100), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
        sa.Column('player_rating', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('effect_config', sa.JSON(), nullable=False),
        sa.Column('rarity_weight', sa.Integer(), nullable=False),
        sa.Column('sell_value', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('player_id', 'edition', 'season_created', name='uq_card_template'),
    )
    op.create_index('idx_card_template_season', 'card_templates', ['season_created'])
    op.create_index('idx_card_template_edition', 'card_templates', ['edition'])
    op.create_index('idx_card_template_player', 'card_templates', ['player_id'])

    # user_cards
    op.create_table(
        'user_cards',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('card_template_id', sa.Integer(), sa.ForeignKey('card_templates.id'), nullable=False),
        sa.Column('acquired_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('acquired_via', sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_user_cards_user', 'user_cards', ['user_id'])
    op.create_index('idx_user_cards_template', 'user_cards', ['card_template_id'])

    # equipped_cards
    op.create_table(
        'equipped_cards',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('slot_number', sa.Integer(), nullable=False),
        sa.Column('user_card_id', sa.Integer(), sa.ForeignKey('user_cards.id'), nullable=False),
        sa.Column('locked', sa.Boolean(), server_default='0', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'season', 'week', 'slot_number', name='uq_equipped_card_slot'),
    )
    op.create_index('idx_equipped_cards_user_week', 'equipped_cards', ['user_id', 'season', 'week'])

    # user_currency
    op.create_table(
        'user_currency',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('balance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lifetime_earned', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lifetime_spent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('user_id'),
    )

    # currency_transactions
    op.create_table(
        'currency_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(30), nullable=False),
        sa.Column('description', sa.String(200), nullable=True),
        sa.Column('season', sa.Integer(), nullable=True),
        sa.Column('week', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_currency_tx_user', 'currency_transactions', ['user_id'])
    op.create_index('idx_currency_tx_user_season', 'currency_transactions', ['user_id', 'season'])
    op.create_index('idx_currency_tx_type', 'currency_transactions', ['transaction_type'])

    # pack_types
    op.create_table(
        'pack_types',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('cost', sa.Integer(), nullable=False),
        sa.Column('cards_per_pack', sa.Integer(), nullable=False),
        sa.Column('guaranteed_rarity', sa.String(20), nullable=True),
        sa.Column('rarity_weights', sa.JSON(), nullable=False),
        sa.Column('description', sa.String(300), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # pack_openings
    op.create_table(
        'pack_openings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('pack_type_id', sa.Integer(), sa.ForeignKey('pack_types.id'), nullable=False),
        sa.Column('cards_received', sa.JSON(), nullable=False),
        sa.Column('cost', sa.Integer(), nullable=False),
        sa.Column('opened_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_pack_openings_user', 'pack_openings', ['user_id'])

    # Add card_bonus_points to fantasy_rosters
    op.add_column('fantasy_rosters', sa.Column('card_bonus_points', sa.Float(), server_default='0.0', nullable=False))


def downgrade() -> None:
    op.drop_column('fantasy_rosters', 'card_bonus_points')
    op.drop_table('pack_openings')
    op.drop_table('pack_types')
    op.drop_table('currency_transactions')
    op.drop_table('user_currency')
    op.drop_table('equipped_cards')
    op.drop_table('user_cards')
    op.drop_table('card_templates')
