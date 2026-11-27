"""OAuth login: passwordless users and their linked provider accounts

Makes `users.password_hash` nullable and adds `oauth_accounts`, which links a
provider's user id to one local user. Downgrade fails while any user has no
password.

Revision ID: 3c7f0a9b2d41
Revises: c85ea1da6073
Create Date: 2026-11-17 17:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3c7f0a9b2d41'
down_revision: Union[str, Sequence[str], None] = 'c85ea1da6073'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Let password_hash be NULL and create the oauth_accounts link table."""
    op.alter_column('users', 'password_hash', nullable=True)
    op.create_table('oauth_accounts',
    sa.Column('provider', sa.String(), nullable=False),
    sa.Column('provider_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('provider', 'provider_id')
    )
    op.create_index(op.f('ix_oauth_accounts_user_id'), 'oauth_accounts', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop the links and require password_hash again; fails while any user has none."""
    op.drop_index(op.f('ix_oauth_accounts_user_id'), table_name='oauth_accounts')
    op.drop_table('oauth_accounts')
    op.alter_column('users', 'password_hash', nullable=False)
