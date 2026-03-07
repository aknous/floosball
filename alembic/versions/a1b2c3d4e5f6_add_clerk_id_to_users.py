"""Add clerk_id to users table

Revision ID: a1b2c3d4e5f6
Revises: c4f9e2b83a17
Create Date: 2026-03-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'c4f9e2b83a17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('clerk_id', sa.String(255), unique=True, nullable=True))
    op.create_index('ix_users_clerk_id', 'users', ['clerk_id'])
    # Make hashed_password nullable (Clerk users don't need it)
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('hashed_password', existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('hashed_password', existing_type=sa.String(255), nullable=False)
    op.drop_index('ix_users_clerk_id', table_name='users')
    op.drop_column('users', 'clerk_id')
