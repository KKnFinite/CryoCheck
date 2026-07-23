"""Validated, read-only Type IV fluid BRIX reference profiles."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping


_REFERENCE_DATA_PATH: Final = (
    Path(__file__).resolve().parent.parent
    / "reference_data"
    / "type4_fluid_brix_ranges.csv"
)
_REFERENCE_HEADERS: Final = ("Fluid", "Minimum BRIX", "Maximum BRIX")


@dataclass(frozen=True, slots=True)
class TypeIVFluidProfile:
    """One immutable Type IV fluid and its inclusive acceptable BRIX range."""

    name: str
    minimum_brix: Decimal
    maximum_brix: Decimal


def load_type4_fluid_profiles(
    reference_path: Path,
) -> Mapping[str, TypeIVFluidProfile]:
    """Load and validate Type IV profiles from one local reference-data file."""
    try:
        reference_file = reference_path.open(
            "r",
            encoding="utf-8",
            newline="",
        )
    except OSError as error:
        raise RuntimeError(
            f"Unable to load Type IV reference data: {reference_path.name}."
        ) from error

    profiles: dict[str, TypeIVFluidProfile] = {}
    with reference_file:
        reader = csv.DictReader(reference_file)
        if tuple(reader.fieldnames or ()) != _REFERENCE_HEADERS:
            raise RuntimeError(
                "Malformed Type IV reference-data headers: "
                f"{reference_path.name}."
            )

        for row_number, row in enumerate(reader, start=2):
            if None in row or set(row) != set(_REFERENCE_HEADERS):
                raise RuntimeError(
                    "Malformed Type IV reference-data row "
                    f"{row_number}: {reference_path.name}."
                )

            fluid_name = row["Fluid"].strip()
            minimum_text = row["Minimum BRIX"].strip()
            maximum_text = row["Maximum BRIX"].strip()
            if not fluid_name or not minimum_text or not maximum_text:
                raise RuntimeError(
                    "Missing Type IV reference-data value on row "
                    f"{row_number}: {reference_path.name}."
                )
            if fluid_name in profiles:
                raise RuntimeError(
                    "Duplicate Type IV reference-data fluid name "
                    f"{fluid_name}: {reference_path.name}."
                )

            try:
                minimum_brix = Decimal(minimum_text)
                maximum_brix = Decimal(maximum_text)
            except InvalidOperation as error:
                raise RuntimeError(
                    "Malformed Type IV reference-data BRIX value on row "
                    f"{row_number}: {reference_path.name}."
                ) from error

            if not minimum_brix.is_finite() or not maximum_brix.is_finite():
                raise RuntimeError(
                    "Non-finite Type IV reference-data BRIX value on row "
                    f"{row_number}: {reference_path.name}."
                )
            if minimum_brix > maximum_brix:
                raise RuntimeError(
                    "Type IV reference-data minimum exceeds maximum on row "
                    f"{row_number}: {reference_path.name}."
                )

            profiles[fluid_name] = TypeIVFluidProfile(
                name=fluid_name,
                minimum_brix=minimum_brix,
                maximum_brix=maximum_brix,
            )

    if not profiles:
        raise RuntimeError(
            f"Type IV reference data contains no profiles: {reference_path.name}."
        )

    return MappingProxyType(profiles)


TYPE4_FLUID_PROFILES: Final[Mapping[str, TypeIVFluidProfile]] = (
    load_type4_fluid_profiles(_REFERENCE_DATA_PATH)
)


def get_type4_fluid_profile(name: str) -> TypeIVFluidProfile | None:
    """Return a registered Type IV profile without database or network access."""
    return TYPE4_FLUID_PROFILES.get(name)


__all__ = [
    "TYPE4_FLUID_PROFILES",
    "TypeIVFluidProfile",
    "get_type4_fluid_profile",
    "load_type4_fluid_profiles",
]
