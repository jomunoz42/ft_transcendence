"""Store the latest deletion challenge per account.

Revision ID: 7c9e2b63d4a1
Revises: c85ea1da6073
"""

from alembic import op
import sqlalchemy as sa

revision = "7c9e2b63d4a1"
down_revision = "c85ea1da6073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "privacy_deletion_requests",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("privacy_deletion_requests")
