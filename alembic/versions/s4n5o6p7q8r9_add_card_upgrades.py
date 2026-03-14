"""Add card upgrade system (The Combine)

Revision ID: s4n5o6p7q8r9
Revises: r3m4n5o6p7q8
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 's4n5o6p7q8r9'
down_revision: Union[str, None] = 'r3m4n5o6p7q8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_upgraded column to card_templates
    op.add_column('card_templates', sa.Column('is_upgraded', sa.Boolean(), server_default='0', nullable=False))

    # Drop old unique constraint, replace with partial unique index
    # (only natural templates enforce uniqueness)
    op.drop_constraint('uq_card_template', 'card_templates', type_='unique')
    op.execute(
        'CREATE UNIQUE INDEX uq_card_template_natural '
        'ON card_templates(player_id, edition, season_created) '
        'WHERE is_upgraded = 0'
    )

    # Create card_upgrade_logs table
    op.create_table(
        'card_upgrade_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('upgrade_type', sa.String(20), nullable=False),
        sa.Column('subject_user_card_id', sa.Integer(), nullable=True),
        sa.Column('offering_user_card_ids', sa.JSON(), nullable=False),
        sa.Column('old_template_id', sa.Integer(), nullable=True),
        sa.Column('new_template_id', sa.Integer(), nullable=False),
        sa.Column('floobits_spent', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_upgrade_log_user', 'card_upgrade_logs', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_upgrade_log_user', table_name='card_upgrade_logs')
    op.drop_table('card_upgrade_logs')
    op.drop_index('uq_card_template_natural', table_name='card_templates')
    op.create_unique_constraint('uq_card_template', 'card_templates', ['player_id', 'edition', 'season_created'])
    op.drop_column('card_templates', 'is_upgraded')
