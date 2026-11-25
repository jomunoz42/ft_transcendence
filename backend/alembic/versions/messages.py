"""messages

Runs after notifications. Creates `messages`: one row per private chat
message. Deleting the sender or the recipient deletes the message; ending a
friendship does not. The first index serves a conversation in both
directions, newest first, with id breaking ties inside one transaction; the
second lets the recipient cascade find rows without a full scan.

Revision ID: c85ea1da6073
Revises: 859639bf8792
Create Date: 2026-11-25 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c85ea1da6073'
down_revision: Union[str, Sequence[str], None] = '859639bf8792'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create messages with its constraints and indexes."""
    op.create_table('messages',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('sender_id', sa.BigInteger(), nullable=False),
    sa.Column('recipient_id', sa.BigInteger(), nullable=False),
    sa.Column('body', sa.String(length=1000), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("body ~ '[^[:space:]]'", name='ck_messages_body_not_blank'),
    sa.CheckConstraint('sender_id <> recipient_id', name='ck_messages_not_self'),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_sender_id_recipient_id_created_at_id', 'messages', ['sender_id', 'recipient_id', 'created_at', 'id'], unique=False)
    op.create_index('ix_messages_recipient_id', 'messages', ['recipient_id'], unique=False)


def downgrade() -> None:
    """Drop messages and its indexes."""
    op.drop_index('ix_messages_recipient_id', table_name='messages')
    op.drop_index('ix_messages_sender_id_recipient_id_created_at_id', table_name='messages')
    op.drop_table('messages')
