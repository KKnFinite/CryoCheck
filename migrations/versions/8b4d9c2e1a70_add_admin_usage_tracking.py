"""Add lightweight admin usage tracking.

Revision ID: 8b4d9c2e1a70
Revises: 4ef8596ab5d2
Create Date: 2026-08-27 19:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "8b4d9c2e1a70"
down_revision = "4ef8596ab5d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "validation_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column("last_validation_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "export_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column("last_export_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("users", "validation_count", server_default=None)
    op.alter_column("users", "export_count", server_default=None)

    usage_totals = op.create_table(
        "usage_totals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "anonymous_validation_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(
        usage_totals,
        [{"id": 1, "anonymous_validation_count": 0}],
    )


def downgrade() -> None:
    op.drop_table("usage_totals")
    op.drop_column("users", "last_export_at")
    op.drop_column("users", "export_count")
    op.drop_column("users", "last_validation_at")
    op.drop_column("users", "validation_count")
