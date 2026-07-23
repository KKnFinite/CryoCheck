"""Focused interpretation of source precipitation text."""

from __future__ import annotations


def has_active_precipitation(source_value: str) -> bool:
    """Return whether source text represents an active precipitation value."""
    normalized = source_value.strip()
    return bool(normalized) and normalized.casefold() != "none"


__all__ = ["has_active_precipitation"]
