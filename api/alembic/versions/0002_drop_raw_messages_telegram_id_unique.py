"""Drop unique constraint on raw_messages.telegram_id.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-27

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the unique constraint; keep a plain index instead
    op.drop_constraint(
        "raw_messages_user_id_telegram_id_key",
        "raw_messages",
        type_="unique",
    )
    op.create_index(
        "ix_raw_messages_telegram_id",
        "raw_messages",
        ["telegram_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_messages_telegram_id", table_name="raw_messages")
    op.create_unique_constraint(
        "raw_messages_user_id_telegram_id_key",
        "raw_messages",
        ["user_id", "telegram_id"],
    )
