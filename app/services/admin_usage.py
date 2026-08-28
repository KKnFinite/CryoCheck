"""Admin authorization and lightweight aggregate usage tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from flask import current_app
from flask_login import current_user

from app.extensions import db
from app.models import UsageTotals, User, normalize_username, utc_now


@dataclass(frozen=True)
class UsageSummary:
    """Aggregate values displayed on the private usage dashboard."""

    total_accounts: int
    accounts_created_7_days: int
    accounts_created_30_days: int
    active_accounts_7_days: int
    active_accounts_30_days: int
    total_validations: int
    signed_in_validations: int
    anonymous_validations: int
    total_exports: int
    signed_in_exports: int
    anonymous_exports: int


def is_admin_user(user=None) -> bool:
    """Return whether an authenticated user matches the configured admin."""
    candidate = current_user if user is None else user
    if not getattr(candidate, "is_authenticated", False):
        return False

    configured = current_app.config.get("CRYOCHECK_ADMIN_USERNAME", "")
    if not isinstance(configured, str) or not configured.strip():
        return False

    return candidate.username_normalized == normalize_username(configured)


def track_completed_validation() -> None:
    """Record one completed audit without retaining anything from its payload."""
    completed_at = utc_now()
    if current_user.is_authenticated:
        current_user.validation_count += 1
        current_user.last_validation_at = completed_at
    else:
        totals = _usage_totals()
        totals.anonymous_validation_count += 1
    db.session.commit()


def track_completed_export() -> None:
    """Record one generated workbook without retaining export content."""
    if current_user.is_authenticated:
        current_user.export_count += 1
        current_user.last_export_at = utc_now()
    else:
        _usage_totals().anonymous_export_count += 1
    db.session.commit()


def build_usage_summary(
    users: tuple[User, ...],
    *,
    anonymous_validations: int,
    anonymous_exports: int,
    now: datetime | None = None,
) -> UsageSummary:
    """Build deterministic dashboard totals from account metadata only."""
    reference_time = _aware_utc(now or utc_now())
    seven_days_ago = reference_time - timedelta(days=7)
    thirty_days_ago = reference_time - timedelta(days=30)

    def created_since(user: User, threshold: datetime) -> bool:
        return _aware_utc(user.created_at) >= threshold

    def active_since(user: User, threshold: datetime) -> bool:
        activity = (
            user.last_login_at,
            user.last_validation_at,
            user.last_export_at,
        )
        return any(
            timestamp is not None and _aware_utc(timestamp) >= threshold
            for timestamp in activity
        )

    signed_in_validations = sum(user.validation_count for user in users)
    signed_in_exports = sum(user.export_count for user in users)
    return UsageSummary(
        total_accounts=len(users),
        accounts_created_7_days=sum(
            created_since(user, seven_days_ago) for user in users
        ),
        accounts_created_30_days=sum(
            created_since(user, thirty_days_ago) for user in users
        ),
        active_accounts_7_days=sum(
            active_since(user, seven_days_ago) for user in users
        ),
        active_accounts_30_days=sum(
            active_since(user, thirty_days_ago) for user in users
        ),
        total_validations=(signed_in_validations + anonymous_validations),
        signed_in_validations=signed_in_validations,
        anonymous_validations=anonymous_validations,
        total_exports=(signed_in_exports + anonymous_exports),
        signed_in_exports=signed_in_exports,
        anonymous_exports=anonymous_exports,
    )


def _usage_totals() -> UsageTotals:
    """Load the one anonymous aggregate, creating it for fresh test schemas."""
    totals = db.session.get(UsageTotals, 1)
    if totals is None:
        totals = UsageTotals(
            id=1,
            anonymous_validation_count=0,
            anonymous_export_count=0,
        )
        db.session.add(totals)
    return totals


def _aware_utc(value: datetime) -> datetime:
    """Normalize database timestamps for reliable SQLite/PostgreSQL comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "UsageSummary",
    "build_usage_summary",
    "is_admin_user",
    "track_completed_export",
    "track_completed_validation",
]
