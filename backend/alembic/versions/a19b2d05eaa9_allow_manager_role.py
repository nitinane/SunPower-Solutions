"""allow manager role

Revision ID: a19b2d05eaa9
Revises: 0e98175dad40
Create Date: 2026-10-31 19:19:09.727035

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a19b2d05eaa9'
down_revision: Union[str, None] = '0e98175dad40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(op.f('ck_users_role_allowed'), 'users', type_='check')
    op.create_check_constraint(
        op.f('ck_users_role_allowed'), 'users',
        "role IN ('admin', 'director', 'support', 'warehouse', 'technician', "
        "'office', 'surveyor', 'manager')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_users_role_allowed'), 'users', type_='check')
    op.create_check_constraint(
        op.f('ck_users_role_allowed'), 'users',
        "role IN ('admin', 'director', 'support', 'warehouse', 'technician', "
        "'office', 'surveyor')",
    )
