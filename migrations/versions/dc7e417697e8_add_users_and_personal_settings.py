"""Add users and personal settings.

Revision ID: dc7e417697e8
Revises:
Create Date: 2026-07-23 00:16:45.657554
"""

from alembic import op
import sqlalchemy as sa


revision = "dc7e417697e8"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=40), nullable=False),
        sa.Column(
            "username_normalized",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_users_username_normalized"),
        "users",
        ["username_normalized"],
        unique=True,
    )

    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "late_entry_threshold_hours",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("type1_fluid", sa.String(length=100), nullable=False),
        sa.Column("type4_fluid", sa.String(length=100), nullable=False),
        sa.Column("allowed_gap_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "max_type1_rate_gpm",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
        ),
        sa.Column(
            "max_type4_rate_gpm",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
        ),
        sa.Column(
            "max_event_time_minutes",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "include_gap_in_event_time",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_settings_user_id"),
        "user_settings",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_settings_user_id"),
        table_name="user_settings",
    )
    op.drop_table("user_settings")
    op.drop_index(
        op.f("ix_users_username_normalized"),
        table_name="users",
    )
    op.drop_table("users")
