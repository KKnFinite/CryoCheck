"""Database models for optional CryoCheck accounts and personal settings."""

from __future__ import annotations

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utc_now() -> datetime:
    """Return an aware UTC timestamp for model defaults."""
    return datetime.now(timezone.utc)


def normalize_username(username: str) -> str:
    """Normalize one already-trimmed account name for unique lookup."""
    return username.strip().lower()


class User(UserMixin, db.Model):
    """Optional local account used to own one private settings record."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), nullable=False)
    username_normalized = db.Column(
        db.String(40),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    settings = db.relationship(
        "UserSettings",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )

    def set_password(self, password: str) -> None:
        """Store a one-way scrypt hash for the supplied password."""
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password: str) -> bool:
        """Verify a password using Werkzeug's supported constant-time helper."""
        return check_password_hash(self.password_hash, password)


class UserSettings(db.Model):
    """One private, editable settings record owned by one user."""

    __tablename__ = "user_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    late_entry_threshold_hours = db.Column(db.Integer, nullable=False)
    type1_fluid = db.Column(db.String(100), nullable=False)
    type4_fluid = db.Column(db.String(100), nullable=False)
    allowed_gap_minutes = db.Column(db.Integer, nullable=False)
    max_type1_rate_gpm = db.Column(db.Numeric(12, 6), nullable=False)
    max_type4_rate_gpm = db.Column(db.Numeric(12, 6), nullable=False)
    max_event_time_minutes = db.Column(db.Integer, nullable=False)
    include_gap_in_event_time = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user = db.relationship("User", back_populates="settings")


__all__ = ["User", "UserSettings", "normalize_username", "utc_now"]
