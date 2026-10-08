"""harden the schema after code review

Runs after sessions. Three fixes, none changing existing data:
- `users.email` must be lowercase (CHECK), so no insert path can store
  "A@x.com" next to "a@x.com".
- Columns with a Python default also get a database default, so plain SQL
  inserts (seed scripts, psql) work.
- Indexes on foreign-key columns, which Postgres never creates on its own, and
  on `sessions.expires_at` for purging expired sessions.

Autogenerate ignores server defaults, so DEFAULTS is written by hand and must
match `server_default=` in models.py.

Revision ID: 4ee1b8f18961
Revises: a62c8bc4b82d
Create Date: 2026-10-08 11:06:05.311828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ee1b8f18961'
down_revision: Union[str, Sequence[str], None] = 'a62c8bc4b82d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULTS = [
    ('users', 'is_verified', sa.text('false')),
    ('users', 'failed_login_count', sa.text('0')),
    ('profiles', 'is_top10_public', sa.text('false')),
    ('profiles', 'is_online', sa.text('false')),
    ('friendships', 'status', sa.text("'pending'")),
    ('songs', 'metadata', sa.text("'{}'")),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint('ck_users_email_lowercase', 'users', 'email = lower(email)')
    for table, column, default in DEFAULTS:
        op.alter_column(table, column, server_default=default)

    op.create_index(op.f('ix_friendships_addressee_id'), 'friendships', ['addressee_id'], unique=False)
    op.create_index(op.f('ix_friendships_requester_id'), 'friendships', ['requester_id'], unique=False)
    op.create_index(op.f('ix_sessions_expires_at'), 'sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_top10_comments_author_id'), 'top10_comments', ['author_id'], unique=False)
    op.create_index(op.f('ix_top10_comments_top10_owner_id'), 'top10_comments', ['top10_owner_id'], unique=False)
    op.create_index(op.f('ix_top10_entries_song_id'), 'top10_entries', ['song_id'], unique=False)
    op.create_index(op.f('ix_top10_reactions_author_id'), 'top10_reactions', ['author_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_top10_reactions_author_id'), table_name='top10_reactions')
    op.drop_index(op.f('ix_top10_entries_song_id'), table_name='top10_entries')
    op.drop_index(op.f('ix_top10_comments_top10_owner_id'), table_name='top10_comments')
    op.drop_index(op.f('ix_top10_comments_author_id'), table_name='top10_comments')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_expires_at'), table_name='sessions')
    op.drop_index(op.f('ix_friendships_requester_id'), table_name='friendships')
    op.drop_index(op.f('ix_friendships_addressee_id'), table_name='friendships')

    for table, column, _ in DEFAULTS:
        op.alter_column(table, column, server_default=None)
    op.drop_constraint('ck_users_email_lowercase', 'users', type_='check')
