"""Add minimum spray-rate settings.

Revision ID: 4ef8596ab5d2
Revises: dc7e417697e8
Create Date: 2026-08-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "4ef8596ab5d2"
down_revision = "dc7e417697e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("min_type1_rate_gpm", sa.Numeric(12, 6), nullable=False, server_default="1"),
    )
    op.add_column(
        "user_settings",
        sa.Column("min_type4_rate_gpm", sa.Numeric(12, 6), nullable=False, server_default="5"),
    )
    op.alter_column("user_settings", "min_type1_rate_gpm", server_default=None)
    op.alter_column("user_settings", "min_type4_rate_gpm", server_default=None)


def downgrade() -> None:
    op.drop_column("user_settings", "min_type4_rate_gpm")
    op.drop_column("user_settings", "min_type1_rate_gpm")
