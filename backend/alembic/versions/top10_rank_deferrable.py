"""top10 rank check deferrable

Make UNIQUE (user_id, rank) on top10_entries DEFERRABLE INITIALLY IMMEDIATE.
A non-deferrable UNIQUE is checked after each row, so one UPDATE that swaps
two ranks fails halfway. DEFERRABLE INITIALLY IMMEDIATE is checked at the end
of each statement instead, so the swap works in place and the ids are kept.
Postgres cannot ALTER a UNIQUE constraint to deferrable, so it is dropped and
recreated.

Revision ID: 70607fbcbe70
Revises: 7c9e2b63d4a1
Create Date: 2026-11-25 15:00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '70607fbcbe70'
down_revision: Union[str, Sequence[str], None] = '7c9e2b63d4a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "top10_entries"
NAME = "top10_entries_user_id_rank_key"


def upgrade() -> None:
    """Recreate the rank unique constraint as deferrable, checked immediately by default."""
    op.drop_constraint(NAME, TABLE, type_="unique")
    op.create_unique_constraint(NAME, TABLE, ["user_id", "rank"], deferrable=True, initially="IMMEDIATE")


def downgrade() -> None:
    """Recreate the rank unique constraint as not deferrable."""
    op.drop_constraint(NAME, TABLE, type_="unique")
    op.create_unique_constraint(NAME, TABLE, ["user_id", "rank"])
