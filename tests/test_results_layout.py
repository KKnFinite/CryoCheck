"""Compact Results-screen presentation coverage."""

from __future__ import annotations

import re
from dataclasses import replace
from html import unescape
from pathlib import Path
from types import SimpleNamespace

from flask import render_template

from app.services.results_display import exception_presentation
from app.services.validation_engine import (
    AuditException,
    AuditResult,
    RuleDetail,
    UnableToEvaluate,
)


_DETAIL_LABELS_BY_RULE = {
    "CC-RULE-001": (
        "Application date/time",
        "Entry date/time",
        "How far before the application event the entry was created",
    ),
    "CC-RULE-002": (
        "Application date/time",
        "Entry date/time",
        "Configured threshold",
        "Actual delay",
        "Amount beyond the threshold",
    ),
    "CC-RULE-003": (
        "Selected Type I fluid",
        "Recorded concentration",
        "Entered freeze point",
        "Expected manufacturer-chart freeze point",
        "Comparison",
    ),
    "CC-RULE-004": (
        "Selected Type I fluid",
        "Recorded concentration",
        "Outside air temperature",
        "Authoritative manufacturer-chart freeze point",
        "Actual calculated buffer",
        "Required buffer",
        "Amount short",
    ),
    "CC-RULE-005": (
        "Selected Type IV fluid",
        "Entered BRIX",
        "Acceptable inclusive range",
        "Range comparison",
        "Amount above nearest boundary",
        "Comparison",
    ),
    "CC-RULE-006": (
        "Type I end time",
        "Type IV start time",
        "Actual calculated gap",
        "Configured Allowed Gap",
        "Amount over setting",
        "Comparison",
    ),
    "CC-RULE-007": (
        "Recorded precipitation",
        "Type IV amount recorded",
        "Finding",
    ),
    "CC-RULE-008": (
        "Type I gallons used",
        "Recorded ProcessTime1",
        "Adjusted calculation time",
        "Adjusted Type I rate",
        "Configured maximum Type I rate",
        "Comparison",
    ),
    "CC-RULE-009": (
        "Type IV gallons used",
        "Recorded ProcessTime4",
        "Adjusted calculation time",
        "Adjusted Type IV rate",
        "Configured maximum Type IV rate",
        "Comparison",
    ),
    "CC-RULE-010": (
        "Type I usage status",
        "Type IV usage status",
        "ProcessTime1",
        "ProcessTime4",
        "Include Gap setting",
        "Included gap",
        "Overlap handling",
        "Calculated event time",
        "Configured maximum event time",
        "Minutes over the maximum",
        "Comparison",
    ),
    "CC-RULE-011": (
        "Selected Type IV fluid",
        "Entered Type IV concentration",
        "Required Type IV concentration",
        "Comparison",
    ),
    "CC-RULE-012": (
        "Original AircraftType",
        "Original TailNumber",
        "Original Notes",
        "Required format",
        "Failure reason",
    ),
    "CC-RULE-013": (
        "Overall StartTime",
        "Overall EndTime",
        "Type I EndTime1",
        "Type IV StartTime4",
        "Calculated overlap",
        "Explanation",
    ),
    "CC-RULE-014": (
        "AircraftType",
        "Type1Used",
        "Type4Used",
        "Current TruckNumber",
        "Original Notes",
        "Missing or failed requirement",
        "Documented truck number",
    ),
}

_EXPECTED_LABELS_BY_RULE = {
    "CC-RULE-001": (
        "Application Date/Time",
        "Entered Early By",
    ),
    "CC-RULE-002": (
        "Application Date/Time",
        "Threshold Overage",
    ),
    "CC-RULE-003": (
        "Entered Freeze Point",
        "Recorded Concentration",
        "Type I Fluid",
        "Correct Freeze Point",
    ),
    "CC-RULE-004": (
        "Recorded Concentration",
        "OAT",
        "Correct Freeze Point",
        "Calculated Buffer",
    ),
    "CC-RULE-005": (
        "Entered BRIX",
        "Type IV Fluid",
        "Acceptable Range",
    ),
    "CC-RULE-006": (
        "Type I End Time",
        "Type IV Start Time",
        "Calculated Gap",
        "Allowed Gap",
    ),
    "CC-RULE-007": (
        "Type IV Used",
        "Precipitation",
        "Expected",
    ),
    "CC-RULE-008": (
        "Adjusted Type I Rate",
        "Type I Used",
        "Process Time 1",
        "Maximum Type I Rate",
    ),
    "CC-RULE-009": (
        "Adjusted Type IV Rate",
        "Type IV Used",
        "Process Time 4",
        "Maximum Type IV Rate",
    ),
    "CC-RULE-010": (
        "Process Time 1",
        "Process Time 4",
        "Include Gap",
        "Included Gap",
        "Overlap Handling",
        "Calculated Event Time",
        "Maximum Event Time",
    ),
    "CC-RULE-011": (
        "Entered Concentration",
        "Required Concentration",
    ),
    "CC-RULE-012": (
        "Entered Tail Number",
        "Aircraft Type",
        "Expected Format",
        "Explanation",
    ),
    "CC-RULE-013": (
        "Type I End Time",
        "Type IV Start Time",
        "Expected",
    ),
    "CC-RULE-014": (
        "Entered Notes",
        "Explanation Requirement",
        "Documented Truck Number",
    ),
}

_INVALID_LABELS_BY_RULE = {
    "CC-RULE-001": ("Entry Date",),
    "CC-RULE-002": ("Entry Date",),
    "CC-RULE-003": ("Entered Freeze Point",),
    "CC-RULE-004": ("Recorded Concentration", "OAT"),
    "CC-RULE-005": ("Entered BRIX",),
    "CC-RULE-006": ("Type I End Time", "Type IV Start Time"),
    "CC-RULE-007": ("Type IV Used",),
    "CC-RULE-008": ("Adjusted Type I Rate",),
    "CC-RULE-009": ("Adjusted Type IV Rate",),
    "CC-RULE-010": ("Process Time 1", "Process Time 4"),
    "CC-RULE-011": ("Entered Concentration",),
    "CC-RULE-012": ("Entered Tail Number",),
    "CC-RULE-013": ("Type I End Time", "Type IV Start Time"),
    "CC-RULE-014": ("Entered Notes",),
}


def _exception(rule_id: str, index: int) -> AuditException:
    details = tuple(
        RuleDetail(label, f"DETAIL-{index:02d}-{detail_index:02d}")
        for detail_index, label in enumerate(
            _DETAIL_LABELS_BY_RULE[rule_id],
            start=1,
        )
    )
    return AuditException(
        rule_id=rule_id,
        rule_name=f"OMIT-RULE-NAME-{index:02d}",
        exception_message=f"EXCEPTION-MESSAGE-{index:02d}",
        source_row_number=index + 1,
        record_id=f"OMIT-RECORD-{index:02d}",
        application_number=f"APPLICATION-{index:02d}",
        gateway_code=f"OMIT-GATEWAY-{index:02d}",
        aircraft_type=f"OMIT-AIRCRAFT-{index:02d}",
        tail_number=f"OMIT-TAIL-{index:02d}",
        application_date=f"OMIT-APPLICATION-DATE-{index:02d}",
        start_time=f"OMIT-START-TIME-{index:02d}",
        date_created=f"2026-07-24 10:{index:02d}",
        truck_number=f"OMIT-TRUCK-{index:02d}",
        operator=f"OMIT-OPERATOR-{index:02d}",
        driver=f"OMIT-DRIVER-{index:02d}",
        details=details,
    )


def _render_results(
    app,
    exceptions: tuple[AuditException, ...],
    *,
    warnings: tuple[UnableToEvaluate, ...] = (),
) -> str:
    audit = AuditResult(
        filename="layout-test.csv",
        rows_audited=len(exceptions) or 1,
        rules_executed=14,
        active_settings_profile_name="Default",
        exceptions=exceptions,
        unable_to_evaluate=warnings,
    )
    import_result = SimpleNamespace(
        unexpected_columns=(),
    )
    export_entries = tuple(
        (
            f"exception-{index}",
            exception,
            exception_presentation(exception),
        )
        for index, exception in enumerate(exceptions, start=1)
    )

    with app.test_request_context("/"):
        return render_template(
            "results.html",
            active_page="import",
            audit=audit,
            import_result=import_result,
            export_available=bool(exceptions),
            export_token="layout-export-token",
            export_entries=export_entries,
        )


def _plain_text(markup: str) -> str:
    return " ".join(
        unescape(re.sub(r"<[^>]+>", " ", markup)).split()
    )


def _visible_text(markup: str) -> str:
    without_hidden_text = re.sub(
        r'<span class="visually-hidden">.*?</span>',
        " ",
        markup,
        flags=re.DOTALL,
    )
    return _plain_text(without_hidden_text)


def _exception_cards(html: str) -> tuple[str, ...]:
    return tuple(
        re.findall(
            r'<article\s+class="exception-card".*?</article>',
            html,
            flags=re.DOTALL,
        )
    )


def test_results_header_is_reduced_to_neofont_title_and_import_action(app):
    html = _render_results(app, (_exception("CC-RULE-001", 1),))
    header = re.search(
        r'<header class="results-heading">.*?</header>',
        html,
        flags=re.DOTALL,
    ).group()

    assert _visible_text(header) == "Audit Results Import Another CSV"
    assert '<h1 id="page-title">Audit Results</h1>' in header
    assert "Audit complete" not in html
    assert "CryoCheck audited every imported row" not in html

    stylesheet = Path("app/static/css/app.css").read_text(encoding="utf-8")
    heading_rule = re.search(
        r"\.results-heading h1 \{.*?\}",
        stylesheet,
        flags=re.DOTALL,
    ).group()
    assert 'font-family: "NeoFont", Arial, sans-serif;' in heading_rule


def test_all_fourteen_rules_use_standard_identity_and_mapped_values(app):
    exceptions = tuple(
        _exception(rule_id, index)
        for index, rule_id in enumerate(_DETAIL_LABELS_BY_RULE, start=1)
    )
    html = _render_results(app, exceptions)
    cards = _exception_cards(html)

    assert len(cards) == 14
    for index, (rule_id, card) in enumerate(
        zip(_DETAIL_LABELS_BY_RULE, cards, strict=True),
        start=1,
    ):
        visible = _visible_text(card)
        assert visible.startswith(f"EXCEPTION-MESSAGE-{index:02d}")
        assert visible.count("Application Number") == 1
        assert visible.count("Entry Date") == 1
        assert f"APPLICATION-{index:02d}" in visible
        assert f"2026-07-24 10:{index:02d}" in visible
        assert visible.index("Application Number") < visible.index("Entry Date")

        for removed in (
            "Record ID",
            "Rule ID",
            "CSV row",
            f"OMIT-RECORD-{index:02d}",
            f"OMIT-TRUCK-{index:02d}",
        ):
            assert removed not in visible
        assert "<dt>Truck Number</dt>" not in card

        assert f'data-rule-id="{rule_id}"' in card
        assert f'data-source-row-number="{index + 1}"' in card
        assert "data-exception-checkbox" in card
        assert 'aria-label="Rule-relevant details"' in card
        top_row_elements = (
            'class="exception-card__top-row"',
            'class="exception-card__selection"',
            'class="exception-card__message"',
            'class="exception-card__identity"',
            'class="exception-details"',
        )
        assert all(element in card for element in top_row_elements)
        positions = tuple(card.index(element) for element in top_row_elements)
        assert positions == tuple(sorted(positions))

        labels = tuple(
            re.findall(
                r'<dt>([^<]+)</dt>',
                re.search(
                    r'<dl class="exception-details".*?</dl>',
                    card,
                    flags=re.DOTALL,
                ).group(),
            )
        )
        assert labels == _EXPECTED_LABELS_BY_RULE[rule_id]
        assert "Comparison" not in labels

        invalid_groups = re.findall(
            r'<(?:div)[^>]*data-display-kind="invalid"[^>]*>.*?</div>',
            card,
            flags=re.DOTALL,
        )
        invalid_labels = tuple(
            re.search(r'<dt>([^<]+)</dt>', group).group(1)
            for group in invalid_groups
        )
        assert invalid_labels == _INVALID_LABELS_BY_RULE[rule_id]

    assert "Select All" in html
    assert "Clear All" in html
    assert "Export Selected" in html
    assert "data-export-all" in html

    stylesheet = Path("app/static/css/app.css").read_text(encoding="utf-8")
    top_row_rule = re.search(
        r"\.exception-card__top-row \{.*?\}",
        stylesheet,
        flags=re.DOTALL,
    ).group()
    assert "display: grid;" in top_row_rule
    assert "minmax(15rem, 1.35fr)" in top_row_rule
    assert "minmax(22rem, 1fr)" in top_row_rule


def test_rule_002_uses_entry_date_as_bad_value_and_one_threshold_sentence(app):
    exception = replace(
        _exception("CC-RULE-002", 2),
        exception_message="Late entry.",
        application_number="APP-2002",
        date_created="1/2/2026 8:08",
        details=(
            RuleDetail("Application date/time", "1/1/2026 5:11"),
            RuleDetail("Entry date/time", "1/2/2026 8:08"),
            RuleDetail("Configured threshold", "24 hours"),
            RuleDetail("Actual delay", "1 day, 2 hours, 57 minutes"),
            RuleDetail(
                "Amount beyond the threshold",
                "2 hours, 57 minutes",
            ),
        ),
    )
    card = _exception_cards(_render_results(app, (exception,)))[0]
    visible = _visible_text(card)

    assert visible == (
        "Late entry. Application Number APP-2002 Entry Date 1/2/2026 8:08 "
        "Application Date/Time 1/1/2026 5:11 Threshold Overage "
        "2 hours, 57 minutes past the 24-hour threshold."
    )
    assert visible.count("1/2/2026 8:08") == 1
    assert "Actual delay" not in visible
    assert "Amount beyond the threshold" not in visible
    assert re.search(
        r'class="exception-card__field result-detail--invalid".*?'
        r'<dt>Entry Date</dt>',
        card,
        flags=re.DOTALL,
    )


def test_rule_003_outside_chart_uses_entered_concentration_as_bad_value(app):
    exception = replace(
        _exception("CC-RULE-003", 3),
        exception_message="Type I concentration outside manufacturer chart.",
        details=(
            RuleDetail("Entered concentration", "90%"),
            RuleDetail("Selected Type I fluid", "Cryotech Polar Plus LT"),
            RuleDetail("Supported chart range", "0–70%"),
            RuleDetail("Comparison", "OMIT-DUPLICATE-COMPARISON"),
        ),
    )
    card = _exception_cards(_render_results(app, (exception,)))[0]
    visible = _visible_text(card)

    assert "Entered Concentration 90%" in visible
    assert "Type I Fluid Cryotech Polar Plus LT" in visible
    assert "Supported Chart Range 0–70%" in visible
    assert "OMIT-DUPLICATE-COMPARISON" not in visible
    assert re.search(
        r'data-display-kind="invalid".*?'
        r'<dt>Entered Concentration</dt>.*?<dd>90%</dd>',
        card,
        flags=re.DOTALL,
    )


def test_rule_012_marks_only_failed_source_fields_as_invalid(app):
    base = _exception("CC-RULE-012", 12)
    notes_failure = replace(
        base,
        details=(
            RuleDetail("Original AircraftType", "0"),
            RuleDetail("Original TailNumber", ""),
            RuleDetail("Original Notes", ""),
            RuleDetail("Required format", "Tail blank; Notes required"),
            RuleDetail(
                "Failure reason",
                "Notes are required for AircraftType 0",
            ),
        ),
    )
    tail_failure = replace(
        base,
        details=(
            RuleDetail("Original AircraftType", "1"),
            RuleDetail("Original TailNumber", "AB-123"),
            RuleDetail("Required format", "UPS NxxxUP format"),
            RuleDetail(
                "Failure reason",
                "Does not match UPS NxxxUP format",
            ),
        ),
    )

    notes_card, tail_card = _exception_cards(
        _render_results(app, (notes_failure, tail_failure))
    )
    assert "Entered Notes Blank" in _visible_text(notes_card)
    assert "Entered Tail Number" not in _visible_text(notes_card)
    assert "Entered Tail Number AB-123" in _visible_text(tail_card)
    assert "Entered Notes" not in _visible_text(tail_card)
    assert "Expected Format" in _visible_text(notes_card)
    assert "Expected Format" not in _visible_text(tail_card)
    assert _visible_text(tail_card).endswith(
        "Aircraft Type 1 Explanation Does not match UPS NxxxUP format"
    )
    assert notes_card.count('data-display-kind="invalid"') == 1
    assert tail_card.count('data-display-kind="invalid"') == 1


def test_rules_007_and_013_use_exact_expected_guidance(app):
    rule_007 = replace(
        _exception("CC-RULE-007", 7),
        details=(
            RuleDetail("Recorded precipitation", "Snow"),
            RuleDetail("Type IV amount recorded", "0"),
            RuleDetail("Finding", "OMIT-RULE-007-FINDING"),
        ),
    )
    rule_013 = replace(
        _exception("CC-RULE-013", 13),
        details=(
            RuleDetail("Type I EndTime1", "20:20"),
            RuleDetail("Type IV StartTime4", "20:15"),
            RuleDetail("Calculated overlap", "5 minutes"),
            RuleDetail("Explanation", "OMIT-DUPLICATE-EXPLANATION"),
        ),
    )

    rule_007_card, rule_013_card = _exception_cards(
        _render_results(app, (rule_007, rule_013))
    )
    assert _visible_text(rule_007_card).endswith(
        "Expected Type IV is expected during active precipitation, or a "
        "comment if another truck was used."
    )
    assert "OMIT-RULE-007-FINDING" not in _visible_text(rule_007_card)
    assert _visible_text(rule_013_card).endswith(
        "Expected Type IV pass cannot start prior to Type I pass ending."
    )
    assert "Calculated Overlap" not in _visible_text(rule_013_card)
    assert "5 minutes" not in _visible_text(rule_013_card)
    assert "OMIT-DUPLICATE-EXPLANATION" not in _visible_text(rule_013_card)


def test_export_form_and_warning_behavior_remain_unchanged(app):
    warning = UnableToEvaluate(
        rule_id="CC-RULE-004",
        rule_name="Type I Freeze-Point Buffer",
        source_row_number=8,
        record_id="WARNING-RECORD",
        invalid_fields=("AmbientTemp", "Type1Used"),
        message="Unable to evaluate this synthetic warning.",
    )
    html = _render_results(
        app,
        (_exception("CC-RULE-003", 3),),
        warnings=(warning,),
    )
    warning_card = re.search(
        r'<li\s+class="audit-warning-card".*?</li>',
        html,
        flags=re.DOTALL,
    ).group()

    assert 'method="post"' in html
    assert 'target="_blank"' in html
    assert html.count('formtarget="_blank"') == 4
    assert html.count("data-export-feedback\n") == 2
    assert "Record ID WARNING-RECORD" in _visible_text(warning_card)
    assert 'data-rule-id="CC-RULE-004"' in warning_card
    assert 'data-source-row-number="8"' in warning_card
    assert "Unable to evaluate AmbientTemp, Type1Used" in _visible_text(
        warning_card
    )
    assert "data-exception-checkbox" not in warning_card
