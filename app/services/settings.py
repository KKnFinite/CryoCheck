"""Immutable defaults and active-settings selection for CryoCheck."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from flask import has_request_context
from flask_login import current_user

from app.models import User, UserSettings


TYPE1_FLUID_OPTIONS: Final[tuple[str, ...]] = ("Cryotech Polar Plus LT",)
TYPE4_FLUID_OPTIONS: Final[tuple[str, ...]] = ("Cryotech Polar Guard Xtend",)


@dataclass(frozen=True, slots=True)
class SettingsDefinition:
    """Read-only settings values used by the active audit profile."""

    name: str
    is_default: bool
    late_entry_threshold_hours: int
    type1_fluid: str
    type4_fluid: str
    allowed_gap_minutes: int
    max_type1_rate_gpm: Decimal
    max_type4_rate_gpm: Decimal
    max_event_time_minutes: int
    include_gap_in_event_time: bool


DEFAULT_SETTINGS: Final = SettingsDefinition(
    name="Default",
    is_default=True,
    late_entry_threshold_hours=24,
    type1_fluid="Cryotech Polar Plus LT",
    type4_fluid="Cryotech Polar Guard Xtend",
    allowed_gap_minutes=5,
    max_type1_rate_gpm=Decimal("60"),
    max_type4_rate_gpm=Decimal("30"),
    max_event_time_minutes=30,
    include_gap_in_event_time=False,
)


def default_model_values() -> dict[str, object]:
    """Return a fresh mapping of built-in defaults for model writes."""
    return {
        "late_entry_threshold_hours": DEFAULT_SETTINGS.late_entry_threshold_hours,
        "type1_fluid": DEFAULT_SETTINGS.type1_fluid,
        "type4_fluid": DEFAULT_SETTINGS.type4_fluid,
        "allowed_gap_minutes": DEFAULT_SETTINGS.allowed_gap_minutes,
        "max_type1_rate_gpm": DEFAULT_SETTINGS.max_type1_rate_gpm,
        "max_type4_rate_gpm": DEFAULT_SETTINGS.max_type4_rate_gpm,
        "max_event_time_minutes": DEFAULT_SETTINGS.max_event_time_minutes,
        "include_gap_in_event_time": DEFAULT_SETTINGS.include_gap_in_event_time,
    }


def create_default_user_settings(user: User) -> UserSettings:
    """Create an unsaved personal record copied from current built-in defaults."""
    return UserSettings(user=user, **default_model_values())


def reset_user_settings(settings: UserSettings) -> None:
    """Copy current built-in defaults into an existing personal record."""
    for field_name, value in default_model_values().items():
        setattr(settings, field_name, value)


def settings_for_user(user: User) -> SettingsDefinition:
    """Return one authenticated user's private settings as an immutable view."""
    if user.settings is None:
        raise RuntimeError("Authenticated user does not have a settings record.")

    settings = user.settings
    return SettingsDefinition(
        name=f"Personal — {user.username}",
        is_default=False,
        late_entry_threshold_hours=settings.late_entry_threshold_hours,
        type1_fluid=settings.type1_fluid,
        type4_fluid=settings.type4_fluid,
        allowed_gap_minutes=settings.allowed_gap_minutes,
        max_type1_rate_gpm=settings.max_type1_rate_gpm,
        max_type4_rate_gpm=settings.max_type4_rate_gpm,
        max_event_time_minutes=settings.max_event_time_minutes,
        include_gap_in_event_time=settings.include_gap_in_event_time,
    )


def get_active_settings(user: User | None = None) -> SettingsDefinition:
    """Select personal settings for a user, otherwise immutable Default."""
    selected_user = user
    if selected_user is None and has_request_context():
        selected_user = current_user

    if selected_user is None or not selected_user.is_authenticated:
        return DEFAULT_SETTINGS

    return settings_for_user(selected_user)


__all__ = [
    "DEFAULT_SETTINGS",
    "SettingsDefinition",
    "TYPE1_FLUID_OPTIONS",
    "TYPE4_FLUID_OPTIONS",
    "create_default_user_settings",
    "default_model_values",
    "get_active_settings",
    "reset_user_settings",
    "settings_for_user",
]
