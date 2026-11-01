"""dispatches.delivered_by

Revision ID: b7c3e1f04d21
Revises: a19b2d05eaa9
Create Date: 2026-11-01 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7c3e1f04d21'
down_revision: Union[str, None] = 'a19b2d05eaa9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('dispatches', sa.Column('delivered_by', sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f('fk_dispatches_delivered_by_users'), 'dispatches', 'users',
        ['delivered_by'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(op.f('fk_dispatches_delivered_by_users'), 'dispatches', type_='foreignkey')
    op.drop_column('dispatches', 'delivered_by')
