"""Collapse card editions from 6 to 4 — wipe all card data for clean start

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-03-24

"""
from alembic import op

# revision identifiers
revision = 'y0z1a2b3c4d5'
down_revision = 'x9y0z1a2b3c4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Wipe all card-related data — closed beta, fresh start with new 4-edition system.
    # Order matters: FK constraints require child tables first.
    op.execute("DELETE FROM equipped_cards")
    op.execute("DELETE FROM featured_shop_cards")
    op.execute("DELETE FROM weekly_card_bonuses")
    op.execute("DELETE FROM card_upgrade_logs")
    op.execute("DELETE FROM user_cards")
    op.execute("DELETE FROM card_templates")


def downgrade() -> None:
    # Data deletion is not reversible — cards will regenerate on next season start.
    pass
