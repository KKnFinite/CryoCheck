"""Validated, read-only Type I manufacturer reference profiles."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping


_REFERENCE_DATA_DIRECTORY: Final = (
    Path(__file__).resolve().parent.parent / "reference_data"
)
_CHART_HEADERS: Final = ("Concentration", "Freezing Point")
_MINIMUM_CONCENTRATION: Final = 0
_MAXIMUM_CONCENTRATION: Final = 70


@dataclass(frozen=True, slots=True)
class TypeIFluidProfile:
    """One immutable Type I fluid and its exact manufacturer freeze points."""

    name: str
    freezing_points: Mapping[int, Decimal]

    def freeze_point_for(self, concentration: int) -> Decimal | None:
        """Return the chart value for a whole concentration, when available."""
        return self.freezing_points.get(concentration)


def _load_profile(
    *,
    name: str,
    chart_path: Path,
    minimum_concentration: int,
    maximum_concentration: int,
) -> TypeIFluidProfile:
    """Load and validate one version-controlled manufacturer chart."""
    try:
        chart_file = chart_path.open(
            "r",
            encoding="utf-8",
            newline="",
        )
    except OSError as error:
        raise RuntimeError(
            f"Unable to load Type I reference chart: {chart_path.name}."
        ) from error

    freeze_points: dict[int, Decimal] = {}
    with chart_file:
        reader = csv.DictReader(chart_file)
        if tuple(reader.fieldnames or ()) != _CHART_HEADERS:
            raise RuntimeError(
                f"Malformed Type I reference chart headers: {chart_path.name}."
            )

        for row_number, row in enumerate(reader, start=2):
            if None in row or set(row) != set(_CHART_HEADERS):
                raise RuntimeError(
                    "Malformed Type I reference chart row "
                    f"{row_number}: {chart_path.name}."
                )

            concentration_text = row["Concentration"]
            freeze_point_text = row["Freezing Point"]
            if not concentration_text or not freeze_point_text:
                raise RuntimeError(
                    "Missing Type I reference chart value on row "
                    f"{row_number}: {chart_path.name}."
                )

            try:
                concentration_decimal = Decimal(concentration_text)
                freeze_point = Decimal(freeze_point_text)
            except InvalidOperation as error:
                raise RuntimeError(
                    "Malformed Type I reference chart value on row "
                    f"{row_number}: {chart_path.name}."
                ) from error

            if (
                not concentration_decimal.is_finite()
                or concentration_decimal
                != concentration_decimal.to_integral_value()
                or not freeze_point.is_finite()
            ):
                raise RuntimeError(
                    "Malformed Type I reference chart value on row "
                    f"{row_number}: {chart_path.name}."
                )

            concentration = int(concentration_decimal)
            if concentration in freeze_points:
                raise RuntimeError(
                    "Duplicate Type I reference chart concentration "
                    f"{concentration}: {chart_path.name}."
                )
            freeze_points[concentration] = freeze_point

    expected_concentrations = set(
        range(minimum_concentration, maximum_concentration + 1)
    )
    if set(freeze_points) != expected_concentrations:
        missing = sorted(expected_concentrations - set(freeze_points))
        unexpected = sorted(set(freeze_points) - expected_concentrations)
        raise RuntimeError(
            "Type I reference chart concentration coverage is invalid "
            f"(missing={missing}, unexpected={unexpected}): {chart_path.name}."
        )

    return TypeIFluidProfile(
        name=name,
        freezing_points=MappingProxyType(freeze_points),
    )


_CRYOTECH_POLAR_PLUS_LT: Final = _load_profile(
    name="Cryotech Polar Plus LT",
    chart_path=(
        _REFERENCE_DATA_DIRECTORY
        / "cryotech_polar_plus_lt_freeze_points.csv"
    ),
    minimum_concentration=_MINIMUM_CONCENTRATION,
    maximum_concentration=_MAXIMUM_CONCENTRATION,
)

TYPE1_FLUID_PROFILES: Final[Mapping[str, TypeIFluidProfile]] = MappingProxyType(
    {_CRYOTECH_POLAR_PLUS_LT.name: _CRYOTECH_POLAR_PLUS_LT}
)


def get_type1_fluid_profile(name: str) -> TypeIFluidProfile | None:
    """Return a registered Type I profile without database or network access."""
    return TYPE1_FLUID_PROFILES.get(name)


__all__ = [
    "TYPE1_FLUID_PROFILES",
    "TypeIFluidProfile",
    "get_type1_fluid_profile",
]
