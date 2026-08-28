"""Signed, in-memory PDF report generation for one CryoCheck audit."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Final
from xml.sax.saxutils import escape

from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.results_display import INVALID_VALUE, exception_presentation
from app.services.validation_engine import AuditResult


_REPORT_SALT: Final = "cryocheck-pdf-report-v1"
_REPORT_VERSION: Final = 1
_NAVY: Final = colors.HexColor("#0B3558")
_GLACIER: Final = colors.HexColor("#EAF7FB")
_ICE: Final = colors.HexColor("#F5FBFD")
_MUTED: Final = colors.HexColor("#526779")
_FAILURE: Final = colors.HexColor("#8A1C2B")
_BORDER: Final = colors.HexColor("#C9E3EC")


class PDFReportRequestError(ValueError):
    """A safe, user-facing PDF report validation failure."""


@dataclass(frozen=True, slots=True)
class PDFReportDetail:
    """One concise visible exception detail."""

    label: str
    value: str
    invalid: bool = False


@dataclass(frozen=True, slots=True)
class PDFReportException:
    """One exception card captured for the downloadable report."""

    message: str
    application_number: str
    entry_date: str
    entry_date_invalid: bool
    details: tuple[PDFReportDetail, ...]


@dataclass(frozen=True, slots=True)
class PDFReportWarning:
    """One unable-to-evaluate warning captured for the report."""

    record_id: str
    invalid_fields: tuple[str, ...]
    message: str


@dataclass(frozen=True, slots=True)
class PDFReportSnapshot:
    """Validated current Results report data safe for PDF rendering."""

    filename: str
    settings_profile: str
    rows_audited: int
    exceptions: tuple[PDFReportException, ...]
    warnings: tuple[PDFReportWarning, ...]
    unexpected_columns: tuple[str, ...]

    @property
    def exception_count(self) -> int:
        return len(self.exceptions)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


@dataclass(frozen=True, slots=True)
class PreparedPDFReport:
    """One signed report token for the current in-memory Results page."""

    token: str


def prepare_pdf_report(
    audit: AuditResult,
    *,
    unexpected_columns: tuple[str, ...],
    secret_key: str,
    context_id: str,
) -> PreparedPDFReport:
    """Capture and sign the exact concise Results presentation."""
    if not context_id:
        raise RuntimeError("A report context is required.")

    exceptions = []
    for exception in audit.exceptions:
        presentation = exception_presentation(exception)
        exceptions.append(
            PDFReportException(
                message=exception.exception_message,
                application_number=(
                    exception.application_number or "Not reported"
                ),
                entry_date=exception.date_created or "Not reported",
                entry_date_invalid=(
                    "entry_date" in presentation.invalid_identity_fields
                ),
                details=tuple(
                    PDFReportDetail(
                        label=detail.label,
                        value=detail.value,
                        invalid=detail.value_kind == INVALID_VALUE,
                    )
                    for detail in presentation.details
                ),
            )
        )

    snapshot = PDFReportSnapshot(
        filename=audit.filename,
        settings_profile=audit.active_settings_profile_name,
        rows_audited=audit.rows_audited,
        exceptions=tuple(exceptions),
        warnings=tuple(
            PDFReportWarning(
                record_id=warning.record_id or "Not reported",
                invalid_fields=warning.invalid_fields,
                message=warning.message,
            )
            for warning in audit.unable_to_evaluate
        ),
        unexpected_columns=unexpected_columns,
    )
    payload = {
        "version": _REPORT_VERSION,
        "context_id": context_id,
        "report": _snapshot_to_payload(snapshot),
    }
    return PreparedPDFReport(token=_serializer(secret_key).dumps(payload))


def load_pdf_report(
    token: str,
    *,
    secret_key: str,
    max_age_seconds: int,
    expected_context_id: str,
) -> PDFReportSnapshot:
    """Verify report age, signature, current-result scope, and schema."""
    if not token:
        raise PDFReportRequestError(
            "The PDF request is missing its audit report. Import the CSV again."
        )
    try:
        payload = _serializer(secret_key).loads(
            token,
            max_age=max_age_seconds,
        )
    except SignatureExpired as error:
        raise PDFReportRequestError(
            "This PDF report expired. Import the CSV again to create a fresh Results page."
        ) from error
    except BadData as error:
        raise PDFReportRequestError(
            "This PDF request is invalid. Import the CSV again."
        ) from error

    if (
        not isinstance(payload, dict)
        or payload.get("version") != _REPORT_VERSION
        or not isinstance(payload.get("context_id"), str)
        or not expected_context_id
        or not hmac.compare_digest(
            payload["context_id"],
            expected_context_id,
        )
    ):
        raise PDFReportRequestError(
            "This PDF request is no longer the current audit result. Import the CSV again."
        )
    try:
        return _snapshot_from_payload(payload["report"])
    except (KeyError, TypeError, ValueError) as error:
        raise PDFReportRequestError(
            "This PDF request is malformed. Import the CSV again."
        ) from error


def build_pdf_report(
    report: PDFReportSnapshot,
    *,
    now: datetime | None = None,
) -> tuple[BytesIO, str]:
    """Generate a styled, downloadable PDF entirely in memory."""
    generated_at = now or datetime.now(timezone.utc)
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        leftMargin=0.48 * inch,
        rightMargin=0.48 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.52 * inch,
        title="CryoCheck Audit Results",
        author="CryoCheck",
        pageCompression=0,
    )
    styles = _report_styles()
    story = [
        Paragraph("CRYOCHECK", styles["brand"]),
        Paragraph("Audit Results", styles["title"]),
        Paragraph(
            f"Generated {generated_at.astimezone(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}",
            styles["generated"],
        ),
        Spacer(1, 0.14 * inch),
        _summary_table(report, styles),
    ]

    if report.unexpected_columns:
        story.extend(
            (
                Spacer(1, 0.09 * inch),
                Paragraph(
                    "<b>Unexpected columns retained:</b> "
                    + escape(", ".join(report.unexpected_columns)),
                    styles["note"],
                ),
            )
        )

    if report.warnings:
        story.extend(
            (
                Spacer(1, 0.22 * inch),
                Paragraph("Unable to Evaluate", styles["section"]),
                Paragraph(
                    (
                        f"{report.warning_count} warning"
                        f"{'s' if report.warning_count != 1 else ''} were separate "
                        "from the exception count."
                    ),
                    styles["section_copy"],
                ),
            )
        )
        for warning in report.warnings:
            story.extend((Spacer(1, 0.07 * inch), _warning_card(warning, styles)))

    story.extend(
        (
            Spacer(1, 0.22 * inch),
            Paragraph("Exceptions", styles["section"]),
            Paragraph(
                f"{report.exception_count} finding{'s' if report.exception_count != 1 else ''} in audit order.",
                styles["section_copy"],
            ),
        )
    )
    if report.exceptions:
        for exception in report.exceptions:
            story.extend((Spacer(1, 0.09 * inch), _exception_card(exception, styles)))
    else:
        story.extend(
            (
                Spacer(1, 0.08 * inch),
                Paragraph(
                    "No exceptions found. All evaluable rows passed the implemented rules.",
                    styles["empty"],
                ),
            )
        )

    document.build(
        story,
        onFirstPage=_page_footer,
        onLaterPages=_page_footer,
    )
    output.seek(0)
    filename = (
        "CryoCheck_Audit_Results_"
        f"{generated_at.strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    return output, filename


def _report_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "CryoCheckBrand",
            parent=sample["Normal"],
            textColor=_NAVY,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            spaceAfter=2,
            tracking=1.2,
        ),
        "title": ParagraphStyle(
            "CryoCheckTitle",
            parent=sample["Title"],
            textColor=_NAVY,
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=26,
            alignment=0,
            spaceAfter=2,
        ),
        "generated": ParagraphStyle(
            "Generated",
            parent=sample["Normal"],
            textColor=_MUTED,
            fontSize=7.5,
            leading=10,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=sample["Heading2"],
            textColor=_NAVY,
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            spaceAfter=1,
        ),
        "section_copy": ParagraphStyle(
            "SectionCopy",
            parent=sample["Normal"],
            textColor=_MUTED,
            fontSize=7.5,
            leading=10,
        ),
        "label": ParagraphStyle(
            "Label",
            parent=sample["Normal"],
            textColor=_MUTED,
            fontName="Helvetica-Bold",
            fontSize=6.2,
            leading=8,
            spaceAfter=2,
            textTransform="uppercase",
        ),
        "value": ParagraphStyle(
            "Value",
            parent=sample["Normal"],
            textColor=_NAVY,
            fontSize=8.2,
            leading=10.5,
        ),
        "invalid": ParagraphStyle(
            "InvalidValue",
            parent=sample["Normal"],
            textColor=_FAILURE,
            fontName="Helvetica-Bold",
            fontSize=8.2,
            leading=10.5,
        ),
        "message": ParagraphStyle(
            "ExceptionMessage",
            parent=sample["Normal"],
            textColor=_NAVY,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
        ),
        "note": ParagraphStyle(
            "Note",
            parent=sample["Normal"],
            textColor=_MUTED,
            fontSize=7.3,
            leading=10,
        ),
        "empty": ParagraphStyle(
            "Empty",
            parent=sample["Normal"],
            textColor=_NAVY,
            backColor=_ICE,
            borderColor=_BORDER,
            borderWidth=0.5,
            borderPadding=9,
            fontSize=8.5,
            leading=12,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=sample["Normal"],
            textColor=_MUTED,
            fontSize=6.5,
            alignment=TA_RIGHT,
        ),
    }


def _summary_table(report: PDFReportSnapshot, styles) -> Table:
    filename = _field("Audited filename", report.filename, styles)
    profile = _field("Settings profile", report.settings_profile, styles)
    rows = _field("Rows audited", str(report.rows_audited), styles)
    exceptions = _field("Total exceptions", str(report.exception_count), styles)
    rows_data = [[filename, profile], [rows, exceptions]]
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, -1), _GLACIER),
        ("BOX", (0, 0), (-1, -1), 0.65, _BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]
    if report.warning_count:
        rows_data.append(
            [_field("Unable to evaluate", str(report.warning_count), styles), ""]
        )
        style_commands.append(("SPAN", (0, 2), (1, 2)))
    table = Table(
        rows_data,
        colWidths=[3.72 * inch, 3.1 * inch],
        hAlign="LEFT",
    )
    table.setStyle(TableStyle(style_commands))
    return table


def _warning_card(warning: PDFReportWarning, styles) -> Table:
    table = Table(
        [
            [
                _field("Record ID", warning.record_id, styles),
                _field(
                    "Unable to evaluate",
                    ", ".join(warning.invalid_fields),
                    styles,
                    invalid=True,
                ),
            ],
            [Paragraph(escape(warning.message), styles["note"]), ""],
        ],
        colWidths=[3.41 * inch, 3.41 * inch],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF9EC")),
                ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#E6C878")),
                ("SPAN", (0, 1), (1, 1)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return KeepTogether(table)


def _exception_card(exception: PDFReportException, styles) -> Table:
    header = Table(
        [
            [
                Paragraph(escape(exception.message), styles["message"]),
                _field(
                    "Entry Date",
                    exception.entry_date,
                    styles,
                    invalid=exception.entry_date_invalid,
                ),
                _field(
                    "Application Number",
                    exception.application_number,
                    styles,
                ),
            ]
        ],
        colWidths=[3.35 * inch, 1.72 * inch, 1.75 * inch],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    detail_rows = []
    for start in range(0, len(exception.details), 4):
        row = [
            _field(detail.label, detail.value, styles, invalid=detail.invalid)
            for detail in exception.details[start : start + 4]
        ]
        row.extend([""] * (4 - len(row)))
        detail_rows.append(row)
    details = Table(
        detail_rows or [[""] * 4],
        colWidths=[1.705 * inch] * 4,
    )
    details.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    card = Table([[header], [details]], colWidths=[6.82 * inch], hAlign="LEFT")
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.65, _BORDER),
                ("LINEBELOW", (0, 0), (-1, 0), 0.35, _BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return KeepTogether(card)


def _field(label: str, value: str, styles, *, invalid: bool = False) -> Table:
    field = Table(
        [
            [Paragraph(escape(label).upper(), styles["label"])],
            [Paragraph(escape(value), styles["invalid" if invalid else "value"])],
        ],
        colWidths=[None],
    )
    field.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return field


def _page_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(_BORDER)
    canvas.setLineWidth(0.45)
    canvas.line(document.leftMargin, 0.36 * inch, letter[0] - document.rightMargin, 0.36 * inch)
    canvas.setFillColor(_MUTED)
    canvas.setFont("Helvetica", 6.5)
    canvas.drawString(document.leftMargin, 0.21 * inch, "CryoCheck Audit Results")
    canvas.drawRightString(
        letter[0] - document.rightMargin,
        0.21 * inch,
        f"Page {document.page}",
    )
    canvas.restoreState()


def _snapshot_to_payload(snapshot: PDFReportSnapshot) -> dict[str, object]:
    return {
        "filename": snapshot.filename,
        "settings_profile": snapshot.settings_profile,
        "rows_audited": snapshot.rows_audited,
        "exceptions": [
            {
                "message": exception.message,
                "application_number": exception.application_number,
                "entry_date": exception.entry_date,
                "entry_date_invalid": exception.entry_date_invalid,
                "details": [
                    {
                        "label": detail.label,
                        "value": detail.value,
                        "invalid": detail.invalid,
                    }
                    for detail in exception.details
                ],
            }
            for exception in snapshot.exceptions
        ],
        "warnings": [
            {
                "record_id": warning.record_id,
                "invalid_fields": list(warning.invalid_fields),
                "message": warning.message,
            }
            for warning in snapshot.warnings
        ],
        "unexpected_columns": list(snapshot.unexpected_columns),
    }


def _snapshot_from_payload(payload: object) -> PDFReportSnapshot:
    if not isinstance(payload, dict):
        raise TypeError("Report must be an object.")
    rows_audited = payload["rows_audited"]
    if type(rows_audited) is not int or rows_audited < 0:
        raise ValueError("Invalid audited row count.")
    exception_payloads = payload["exceptions"]
    warning_payloads = payload["warnings"]
    unexpected_payload = payload["unexpected_columns"]
    if not all(
        isinstance(value, list)
        for value in (exception_payloads, warning_payloads, unexpected_payload)
    ):
        raise TypeError("Invalid report collections.")
    return PDFReportSnapshot(
        filename=_required_string(payload, "filename"),
        settings_profile=_required_string(payload, "settings_profile"),
        rows_audited=rows_audited,
        exceptions=tuple(_exception_from_payload(item) for item in exception_payloads),
        warnings=tuple(_warning_from_payload(item) for item in warning_payloads),
        unexpected_columns=tuple(_string_item(item) for item in unexpected_payload),
    )


def _exception_from_payload(payload: object) -> PDFReportException:
    if not isinstance(payload, dict) or type(payload.get("entry_date_invalid")) is not bool:
        raise TypeError("Invalid report exception.")
    detail_payloads = payload["details"]
    if not isinstance(detail_payloads, list):
        raise TypeError("Invalid report details.")
    return PDFReportException(
        message=_required_string(payload, "message"),
        application_number=_required_string(payload, "application_number"),
        entry_date=_required_string(payload, "entry_date"),
        entry_date_invalid=payload["entry_date_invalid"],
        details=tuple(_detail_from_payload(item) for item in detail_payloads),
    )


def _detail_from_payload(payload: object) -> PDFReportDetail:
    if not isinstance(payload, dict) or type(payload.get("invalid")) is not bool:
        raise TypeError("Invalid report detail.")
    return PDFReportDetail(
        label=_required_string(payload, "label"),
        value=_required_string(payload, "value"),
        invalid=payload["invalid"],
    )


def _warning_from_payload(payload: object) -> PDFReportWarning:
    if not isinstance(payload, dict) or not isinstance(payload.get("invalid_fields"), list):
        raise TypeError("Invalid report warning.")
    return PDFReportWarning(
        record_id=_required_string(payload, "record_id"),
        invalid_fields=tuple(_string_item(item) for item in payload["invalid_fields"]),
        message=_required_string(payload, "message"),
    )


def _required_string(payload: dict, key: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a nonblank string.")
    return value


def _string_item(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Report collection values must be nonblank strings.")
    return value


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    if not secret_key:
        raise RuntimeError("A secret key is required for PDF reports.")
    return URLSafeTimedSerializer(secret_key, salt=_REPORT_SALT)


__all__ = [
    "PDFReportRequestError",
    "PDFReportSnapshot",
    "PreparedPDFReport",
    "build_pdf_report",
    "load_pdf_report",
    "prepare_pdf_report",
]
