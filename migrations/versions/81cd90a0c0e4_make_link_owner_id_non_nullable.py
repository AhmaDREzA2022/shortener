"""make link owner_id non-nullable

Revision ID: 81cd90a0c0e4
Revises: eeff38637f12
Create Date: 2026-09-28 02:26:06.537901

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "81cd90a0c0e4"
down_revision: Union[str, Sequence[str], None] = "eeff38637f12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("fk_links_owner_id_users", "links", type_="foreignkey")
    op.alter_column("links", "owner_id", existing_type=sa.BigInteger(), nullable=False)
    op.create_foreign_key(
        "fk_links_owner_id_users",
        "links",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_links_owner_id_users", "links", type_="foreignkey")
    op.alter_column("links", "owner_id", existing_type=sa.BigInteger(), nullable=True)
    op.create_foreign_key(
        "fk_links_owner_id_users",
        "links",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
