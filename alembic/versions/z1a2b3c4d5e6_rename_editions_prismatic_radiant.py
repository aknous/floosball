"""Rename card edition: gold -> prismatic

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-03-25

"""
from alembic import op

# revision identifiers
revision = 'z1a2b3c4d5e6'
down_revision = 'y0z1a2b3c4d5'
branch_labels = None
depends_on = None


def upgrade():
    # Rename gold -> prismatic in card_templates
    op.execute("UPDATE card_templates SET edition = 'prismatic' WHERE edition = 'gold'")

    # Rename gold -> prismatic in pack_types rarity_weights JSON
    op.execute("""
        UPDATE pack_types
        SET rarity_weights = REPLACE(rarity_weights, '"gold"', '"prismatic"')
        WHERE rarity_weights LIKE '%gold%'
    """)
    op.execute("UPDATE pack_types SET guaranteed_rarity = 'prismatic' WHERE guaranteed_rarity = 'gold'")


def downgrade():
    op.execute("UPDATE card_templates SET edition = 'gold' WHERE edition = 'prismatic'")
    op.execute("""
        UPDATE pack_types
        SET rarity_weights = REPLACE(rarity_weights, '"prismatic"', '"gold"')
        WHERE rarity_weights LIKE '%prismatic%'
    """)
    op.execute("UPDATE pack_types SET guaranteed_rarity = 'gold' WHERE guaranteed_rarity = 'prismatic'")
