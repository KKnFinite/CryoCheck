"""Add anonymous export usage tracking.

Revision ID: c9d6e1a4b352
Revises: 8b4d9c2e1a70
Create Date: 2026-08-28 01:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c9d6e1a4b352"
down_revision = "8b4d9c2e1a70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usage_totals",
        sa.Column(
            "anonymous_export_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.alter_column(
        "usage_totals",
        "anonymous_export_count",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("usage_totals", "anonymous_export_count")
