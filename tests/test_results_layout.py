"""Compact Results-screen rendering coverage."""

from __future__ import annotations

import re
from html import unescape
from types import SimpleNamespace

from flask import render_template

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
        record_id=f"RECORD-{index:02d}",
        application_number=f"OMIT-APPLICATION-{index:02d}",
        gateway_code=f"OMIT-GATEWAY-{index:02d}",
        aircraft_type=f"OMIT-AIRCRAFT-{index:02d}",
        tail_number=f"OMIT-TAIL-{index:02d}",
        application_date=f"OMIT-APPLICATION-DATE-{index:02d}",
        start_time=f"OMIT-START-TIME-{index:02d}",
        date_created=f"2026-07-24 10:{index:02d}",
        truck_number=f"TRUCK-{index:02d}",
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
        preview_records=(),
    )
    export_entries = tuple(
        (f"exception-{index}", exception)
        for index, exception in enumerate(exceptions, start=1)
    )

    with app.test_request_context("/"):
        return render_template(
            "results.html",
            active_page="import",
            audit=audit,
            import_result=import_result,
            preview_columns=(),
            export_available=bool(exceptions),
            export_token="layout-export-token",
            export_entries=export_entries,
        )


def _plain_text(markup: str) -> str:
    return " ".join(
        unescape(re.sub(r"<[^>]+>", " ", markup)).split()
    )


def test_all_fourteen_rules_render_compact_identity_and_relevant_details(app):
    exceptions = tuple(
        _exception(rule_id, index)
        for index, rule_id in enumerate(_DETAIL_LABELS_BY_RULE, start=1)
    )
    html = _render_results(app, exceptions)
    rule_ids = tuple(
        re.findall(r">CC-RULE-\d{3}<", html)
    )
    rule_ids = tuple(rule_id[1:-1] for rule_id in rule_ids)
    cards = tuple(
        re.findall(
            r'<article\s+class="exception-card".*?</article>',
            html,
            flags=re.DOTALL,
        )
    )

    assert rule_ids == tuple(_DETAIL_LABELS_BY_RULE)
    assert len(cards) == 14

    for index, (rule_id, card) in enumerate(
        zip(rule_ids, cards, strict=True),
        start=1,
    ):
        card_text = _plain_text(card)
        required_elements = (
            "data-exception-checkbox",
            "Record ID",
            "Entry Date",
            "Truck Number",
            "Rule ID",
            "Exception",
            'aria-label="Rule-relevant details"',
        )

        assert all(element in card for element in required_elements)
        assert tuple(card.index(element) for element in required_elements) == (
            *sorted(card.index(element) for element in required_elements),
        )
        assert f"RECORD-{index:02d}" in card_text
        assert f"2026-07-24 10:{index:02d}" in card_text
        assert f"TRUCK-{index:02d}" in card_text
        assert rule_id in card_text
        assert f"EXCEPTION-MESSAGE-{index:02d}" in card_text
        assert f"CSV row {index + 1}" in card_text

        for detail_index, label in enumerate(
            _DETAIL_LABELS_BY_RULE[rule_id],
            start=1,
        ):
            assert label in card_text
            assert f"DETAIL-{index:02d}-{detail_index:02d}" in card_text

        for omitted_value in (
            f"OMIT-RULE-NAME-{index:02d}",
            f"OMIT-APPLICATION-{index:02d}",
            f"OMIT-GATEWAY-{index:02d}",
            f"OMIT-AIRCRAFT-{index:02d}",
            f"OMIT-TAIL-{index:02d}",
            f"OMIT-APPLICATION-DATE-{index:02d}",
            f"OMIT-START-TIME-{index:02d}",
            f"OMIT-OPERATOR-{index:02d}",
            f"OMIT-DRIVER-{index:02d}",
        ):
            assert omitted_value not in card_text

    assert "Select All" in html
    assert "Clear All" in html
    assert "Export Selected" in html
    assert "data-export-all" in html


def test_unable_to_evaluate_warnings_remain_separate_and_compact(app):
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
        (_exception("CC-RULE-001", 1),),
        warnings=(warning,),
    )
    warning_card = re.search(
        r'<li class="audit-warning-card">.*?</li>',
        html,
        flags=re.DOTALL,
    )

    assert warning_card is not None
    warning_text = _plain_text(warning_card.group())
    assert "Record ID WARNING-RECORD CSV row 8" in warning_text
    assert "Rule ID CC-RULE-004" in warning_text
    assert "Unable to evaluate AmbientTemp, Type1Used" in warning_text
    assert "Unable to evaluate this synthetic warning." in warning_text
    assert html.index("audit-warning-summary") < html.index(
        'id="exception-export-form"'
    )
    assert "data-exception-checkbox" not in warning_card.group()
