"""avatars

Runs after notifications. Creates `avatars`: one re-encoded image per user,
deleted with the user. `profiles.avatar_url` becomes NOT NULL with the
default avatar URL, and existing NULL or hand-set values are reset to it,
since only an upload may point it at an image.

Revision ID: 5b7b1c7e545c
Revises: 859639bf8792
Create Date: 2026-11-25 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5b7b1c7e545c'
down_revision: Union[str, Sequence[str], None] = '859639bf8792'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_URL = '/api/v1/avatars/default'


def upgrade() -> None:
    """Create avatars, reset every avatar_url to the default and make it required."""
    op.create_table('avatars',
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.execute(sa.text("UPDATE profiles SET avatar_url = :url").bindparams(url=DEFAULT_URL))
    op.alter_column('profiles', 'avatar_url', nullable=False, server_default=sa.text(f"'{DEFAULT_URL}'"))


def downgrade() -> None:
    """Drop avatars and let avatar_url be NULL again, with no default."""
    op.alter_column('profiles', 'avatar_url', nullable=True, server_default=None)
    op.drop_table('avatars')
