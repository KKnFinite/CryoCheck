"""In-memory parsing for CryoCheck deicing-log CSV uploads."""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath

import pandas as pd
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


EXPECTED_COLUMNS = (
    "RecordID",
    "ApplicationNumber",
    "GatewayUID",
    "GatewayCode",
    "RRDD",
    "ApplicationDate",
    "StartTime",
    "EndTime",
    "ElapsedTime",
    "ModifiedBy",
    "ModifiedByName",
    "LastModified",
    "CreatedBy",
    "CreatedByName",
    "DateCreated",
    "AircraftType",
    "TailNumber",
    "Reason",
    "Precipitation",
    "AmbientTemp",
    "DewPoint",
    "OtherConditions",
    "EquipmentOwnedBy",
    "ConductedBy",
    "TruckNumber",
    "Operator",
    "Driver",
    "Posted",
    "VendorName",
    "AuthorizedBy",
    "DialToTemperatureTruck",
    "DateCreatedUTC",
    "LastModifiedUTC",
    "LiquidUOM",
    "TempUOM",
    "Type1Used",
    "Type1SKU",
    "Type1Concentration",
    "FreezingPoint1",
    "StartTime1",
    "EndTime1",
    "ProcessTime1",
    "FromInventory1",
    "ForcedAir1",
    "LowFlow1",
    "Type4Used",
    "Type4SKU",
    "Type4AConcentration",
    "FreezingPoint4",
    "StartTime4",
    "EndTime4",
    "ProcessTime4",
    "FromInventory4",
    "ForcedAir4",
    "LowFlow4",
    "Type4ABrix",
    "Notes",
)

PREVIEW_COLUMNS = (
    "RecordID",
    "ApplicationNumber",
    "GatewayCode",
    "ApplicationDate",
    "StartTime",
    "AircraftType",
    "TailNumber",
    "TruckNumber",
    "Operator",
    "Driver",
    "Type1Used",
    "Type1Concentration",
    "FreezingPoint1",
    "Type4Used",
    "Type4ABrix",
)

PREVIEW_DISPLAY_COLUMNS = ("CSV Row", *PREVIEW_COLUMNS)
PREVIEW_ROW_LIMIT = 10


@dataclass(frozen=True, slots=True)
class CSVSourceRow:
    """One immutable CSV row with its original fields and physical row number."""

    source_row_number: int
    fields: tuple[tuple[str, str], ...]

    def get(self, column_name: str, default: str = "") -> str:
        """Return an original source value without normalizing it."""
        for name, value in self.fields:
            if name == column_name:
                return value
        return default


@dataclass(frozen=True, slots=True)
class CSVImportResult:
    """Complete in-memory source data and safe presentation details."""

    filename: str
    row_count: int
    column_count: int
    column_names: tuple[str, ...]
    rows: tuple[CSVSourceRow, ...]
    expected_columns_found: tuple[str, ...]
    missing_columns: tuple[str, ...]
    unexpected_columns: tuple[str, ...]
    gateway_codes: tuple[str, ...]
    earliest_application_date: str | None
    latest_application_date: str | None
    preview_records: tuple[dict[str, str | int], ...]


class CSVImportError(ValueError):
    """A user-safe CSV rejection with optional schema details."""

    def __init__(
        self,
        message: str,
        *,
        filename: str | None = None,
        missing_columns: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.message = message
        self.filename = filename
        self.missing_columns = missing_columns


def parse_csv_upload(upload: FileStorage | None) -> CSVImportResult:
    """Validate and parse one CSV upload without retaining its contents."""
    if upload is None or not upload.filename:
        raise CSVImportError("Choose a CSV file to import.")

    raw_filename = upload.filename
    display_filename = _safe_display_filename(raw_filename)
    file_suffix = PurePosixPath(raw_filename.replace("\\", "/")).suffix.lower()
    if file_suffix != ".csv":
        raise CSVImportError(
            "CryoCheck accepts one file with a .csv extension.",
            filename=display_filename,
        )

    payload = upload.stream.read()
    if not payload or not payload.strip():
        raise CSVImportError(
            "The selected CSV file is empty.",
            filename=display_filename,
        )

    try:
        csv_text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CSVImportError(
            "The CSV text could not be decoded. Export it as UTF-8 and try again.",
            filename=display_filename,
        ) from None

    if not csv_text.strip():
        raise CSVImportError(
            "The selected CSV file is empty.",
            filename=display_filename,
        )

    if "\x00" in csv_text:
        raise CSVImportError(
            "The file does not contain supported CSV text.",
            filename=display_filename,
        )

    header, source_rows = _inspect_csv_structure(
        csv_text,
        display_filename,
    )
    duplicate_columns = tuple(
        name for name, count in Counter(header).items() if count > 1
    )
    if duplicate_columns:
        duplicate_labels = ", ".join(name or "(blank column)" for name in duplicate_columns)
        raise CSVImportError(
            f"The CSV contains duplicate column names: {duplicate_labels}.",
            filename=display_filename,
        )

    missing_columns = tuple(name for name in EXPECTED_COLUMNS if name not in header)
    if missing_columns:
        raise CSVImportError(
            "The CSV is missing required CryoCheck columns.",
            filename=display_filename,
            missing_columns=missing_columns,
        )

    try:
        dataframe = pd.read_csv(
            io.StringIO(csv_text),
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            on_bad_lines="error",
            low_memory=False,
        )
    except (pd.errors.EmptyDataError, pd.errors.ParserError, ValueError):
        raise CSVImportError(
            "The file could not be parsed as a valid CSV. Check its rows and quoting.",
            filename=display_filename,
        ) from None

    if dataframe.empty:
        raise CSVImportError(
            "The CSV contains a header but no data rows.",
            filename=display_filename,
        )

    if len(dataframe.index) != len(source_rows):
        raise CSVImportError(
            "The file could not be parsed as a consistent CSV.",
            filename=display_filename,
        )

    unexpected_columns = tuple(name for name in header if name not in EXPECTED_COLUMNS)
    gateway_codes = tuple(
        dict.fromkeys(
            str(value)
            for value in dataframe["GatewayCode"].tolist()
            if str(value).strip()
        )
    )
    earliest_date, latest_date = _application_date_range(
        dataframe["ApplicationDate"]
    )
    preview_records = _build_preview(source_rows)

    return CSVImportResult(
        filename=display_filename,
        row_count=len(dataframe.index),
        column_count=len(dataframe.columns),
        column_names=header,
        rows=source_rows,
        expected_columns_found=tuple(
            name for name in EXPECTED_COLUMNS if name in dataframe.columns
        ),
        missing_columns=(),
        unexpected_columns=unexpected_columns,
        gateway_codes=gateway_codes,
        earliest_application_date=earliest_date,
        latest_application_date=latest_date,
        preview_records=preview_records,
    )


def _safe_display_filename(raw_filename: str) -> str:
    safe_name = secure_filename(PurePosixPath(raw_filename.replace("\\", "/")).name)
    if not safe_name or "." not in safe_name:
        return "uploaded.csv"
    return safe_name


def _inspect_csv_structure(
    csv_text: str,
    filename: str,
) -> tuple[tuple[str, ...], tuple[CSVSourceRow, ...]]:
    reader = csv.reader(io.StringIO(csv_text, newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration:
        raise CSVImportError(
            "The selected CSV file is empty.",
            filename=filename,
        ) from None
    except csv.Error:
        raise CSVImportError(
            "The CSV header is malformed or incomplete.",
            filename=filename,
        ) from None

    if not header or all(not name for name in header):
        raise CSVImportError(
            "The CSV does not contain a usable header row.",
            filename=filename,
        )

    source_rows: list[CSVSourceRow] = []
    previous_line_end = reader.line_num
    try:
        for row in reader:
            row_start = previous_line_end + 1
            previous_line_end = reader.line_num
            if not row:
                continue
            if len(row) != len(header):
                raise CSVImportError(
                    "The CSV contains a row with a different number of fields than its header.",
                    filename=filename,
                )
            source_rows.append(
                CSVSourceRow(
                    source_row_number=row_start,
                    fields=tuple(zip(header, row, strict=True)),
                )
            )
    except csv.Error:
        raise CSVImportError(
            "The CSV contains malformed quoting or an incomplete row.",
            filename=filename,
        ) from None

    return tuple(header), tuple(source_rows)


def _application_date_range(
    application_dates: pd.Series,
) -> tuple[str | None, str | None]:
    display_values = application_dates.astype(str)
    nonblank_values = display_values.where(display_values.str.strip().ne(""))
    parsed_values = pd.to_datetime(
        nonblank_values,
        errors="coerce",
        format="mixed",
        utc=True,
    )
    readable_values = parsed_values.dropna()
    if readable_values.empty:
        return None, None

    earliest_index = readable_values.idxmin()
    latest_index = readable_values.idxmax()
    return (
        str(display_values.loc[earliest_index]),
        str(display_values.loc[latest_index]),
    )


def _build_preview(
    source_rows: tuple[CSVSourceRow, ...],
) -> tuple[dict[str, str | int], ...]:
    preview_records: list[dict[str, str | int]] = []

    for source_row in source_rows[:PREVIEW_ROW_LIMIT]:
        preview_record: dict[str, str | int] = {
            "CSV Row": source_row.source_row_number
        }
        preview_record.update(
            {
                column: source_row.get(column)
                for column in PREVIEW_COLUMNS
            }
        )
        preview_records.append(preview_record)

    return tuple(preview_records)


__all__ = [
    "CSVImportError",
    "CSVImportResult",
    "CSVSourceRow",
    "EXPECTED_COLUMNS",
    "PREVIEW_DISPLAY_COLUMNS",
    "parse_csv_upload",
]
