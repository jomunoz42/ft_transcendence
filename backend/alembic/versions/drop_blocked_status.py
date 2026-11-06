"""drop 'blocked' from friendship status

Runs after blocks. Moves every friendship with status 'blocked' into `blocks`
(the requester becomes the blocker), deletes those friendships, then narrows
`ck_friendships_status` to pending, accepted and declined. Downgrade widens the
constraint again but leaves the moved rows in `blocks`.

Revision ID: 1ee21ffe2e6a
Revises: 0b39de5262b6
Create Date: 2026-11-06 15:56:31

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '1ee21ffe2e6a'
down_revision: Union[str, Sequence[str], None] = '0b39de5262b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Move blocked friendships into blocks, then forbid the 'blocked' status."""
    op.execute("""
        INSERT INTO blocks (blocker_id, blocked_id)
        SELECT requester_id, addressee_id FROM friendships WHERE status = 'blocked'
        ON CONFLICT DO NOTHING
    """)
    op.execute("DELETE FROM friendships WHERE status = 'blocked'")
    op.drop_constraint('ck_friendships_status', 'friendships', type_='check')
    op.create_check_constraint(
        'ck_friendships_status', 'friendships',
        "status IN ('pending', 'accepted', 'declined')",
    )


def downgrade() -> None:
    """Allow 'blocked' again; rows already moved into blocks stay there."""
    op.drop_constraint('ck_friendships_status', 'friendships', type_='check')
    op.create_check_constraint(
        'ck_friendships_status', 'friendships',
        "status IN ('pending', 'accepted', 'declined', 'blocked')",
    )
