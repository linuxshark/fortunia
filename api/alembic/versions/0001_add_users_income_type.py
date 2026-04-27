"""Add users table, expenses.type, categories.applicable_to, rebuild monthly_summaries.

Revision ID: 0001
Revises:
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("display_name", sa.String(50), nullable=False),
        sa.Column("user_key", sa.String(50), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # 2. expenses.type column
    op.add_column(
        "expenses",
        sa.Column(
            "type",
            sa.String(10),
            nullable=False,
            server_default="expense",
        ),
    )
    op.create_check_constraint(
        "ck_expenses_type",
        "expenses",
        "type IN ('expense', 'income')",
    )

    # 3. categories.applicable_to column
    op.add_column(
        "categories",
        sa.Column(
            "applicable_to",
            sa.String(10),
            nullable=False,
            server_default="expense",
        ),
    )
    op.create_check_constraint(
        "ck_categories_applicable_to",
        "categories",
        "applicable_to IN ('expense', 'income', 'both')",
    )

    # 4. Seed initial user
    op.execute("""
        INSERT INTO users (telegram_id, display_name, user_key)
        VALUES (757348065, 'Raúl Linares', 'raul')
        ON CONFLICT (telegram_id) DO NOTHING
    """)

    # 5. Rebuild monthly_summaries to include type
    op.execute("DROP MATERIALIZED VIEW IF EXISTS monthly_summaries")
    op.execute("""
        CREATE MATERIALIZED VIEW monthly_summaries AS
        SELECT
            user_id,
            date_trunc('month', spent_at) AS month,
            type,
            category_id,
            COUNT(*)    AS count,
            SUM(amount) AS total,
            AVG(amount) AS avg
        FROM expenses
        GROUP BY user_id, date_trunc('month', spent_at), type, category_id
    """)
    op.execute("""
        CREATE UNIQUE INDEX ON monthly_summaries(user_id, month, type, category_id)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS monthly_summaries")
    op.execute("""
        CREATE MATERIALIZED VIEW monthly_summaries AS
        SELECT
            user_id,
            date_trunc('month', spent_at) AS month,
            category_id,
            COUNT(*)    AS count,
            SUM(amount) AS total,
            AVG(amount) AS avg
        FROM expenses
        GROUP BY user_id, date_trunc('month', spent_at), category_id
    """)
    op.execute("CREATE UNIQUE INDEX ON monthly_summaries(user_id, month, category_id)")
    op.drop_constraint("ck_categories_applicable_to", "categories")
    op.drop_column("categories", "applicable_to")
    op.drop_constraint("ck_expenses_type", "expenses")
    op.drop_column("expenses", "type")
    op.drop_table("users")
