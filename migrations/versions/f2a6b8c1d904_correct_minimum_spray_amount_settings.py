"""Correct minimum spray settings to total gallons.

Revision ID: f2a6b8c1d904
Revises: c9d6e1a4b352
Create Date: 2026-08-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f2a6b8c1d904"
down_revision = "c9d6e1a4b352"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "min_type1_gallons",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "min_type4_gallons",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="5",
        ),
    )
    op.alter_column("user_settings", "min_type1_gallons", server_default=None)
    op.alter_column("user_settings", "min_type4_gallons", server_default=None)
    op.drop_column("user_settings", "min_type4_rate_gpm")
    op.drop_column("user_settings", "min_type1_rate_gpm")


def downgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "min_type1_rate_gpm",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "user_settings",
        sa.Column(
            "min_type4_rate_gpm",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="5",
        ),
    )
    op.alter_column("user_settings", "min_type1_rate_gpm", server_default=None)
    op.alter_column("user_settings", "min_type4_rate_gpm", server_default=None)
    op.drop_column("user_settings", "min_type4_gallons")
    op.drop_column("user_settings", "min_type1_gallons")
