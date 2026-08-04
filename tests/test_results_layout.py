"""Compact Results-screen rendering coverage."""

from __future__ import annotations

import re
from dataclasses import replace
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

_DISPLAY_DETAIL_LABELS_BY_RULE = {
    "CC-RULE-001": (
        "Application date/time",
        "How far before the application event the entry was created",
    ),
    "CC-RULE-002": (),
    "CC-RULE-003": ("Comparison",),
    "CC-RULE-004": (),
    "CC-RULE-005": ("Comparison",),
    "CC-RULE-006": ("Comparison",),
    "CC-RULE-007": (
        "Recorded precipitation",
        "Type IV amount recorded",
    ),
    "CC-RULE-008": (
        "Type I gallons used",
        "Recorded ProcessTime1",
        "Adjusted calculation time",
        "Comparison",
    ),
    "CC-RULE-009": (
        "Type IV gallons used",
        "Recorded ProcessTime4",
        "Adjusted calculation time",
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
        "Comparison",
    ),
    "CC-RULE-011": ("Comparison",),
    "CC-RULE-012": (
        "Original AircraftType",
        "Original TailNumber",
        "Original Notes",
        "Required format",
        "Failure reason",
    ),
    "CC-RULE-013": ("Explanation",),
    "CC-RULE-014": (
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
    from app.services.results_display import concise_exception_details

    export_entries = tuple(
        (
            f"exception-{index}",
            exception,
            concise_exception_details(exception),
        )
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


def _visible_text(markup: str) -> str:
    without_hidden_text = re.sub(
        r'<span class="visually-hidden">.*?</span>',
        " ",
        markup,
        flags=re.DOTALL,
    )
    return _plain_text(without_hidden_text)


def test_all_fourteen_rules_render_compact_identity_and_relevant_details(app):
    exceptions = tuple(
        _exception(rule_id, index)
        for index, rule_id in enumerate(_DETAIL_LABELS_BY_RULE, start=1)
    )
    html = _render_results(app, exceptions)
    cards = tuple(
        re.findall(
            r'<article\s+class="exception-card".*?</article>',
            html,
            flags=re.DOTALL,
        )
    )

    assert len(cards) == 14
    rule_ids = tuple(
        re.search(r'data-rule-id="(CC-RULE-\d{3})"', card).group(1)
        for card in cards
    )
    assert rule_ids == tuple(_DETAIL_LABELS_BY_RULE)

    for index, (rule_id, card) in enumerate(
        zip(rule_ids, cards, strict=True),
        start=1,
    ):
        card_text = _visible_text(card)
        required_elements = (
            "data-exception-checkbox",
            f"EXCEPTION-MESSAGE-{index:02d}",
            "Record ID",
            "Entry Date",
            "Truck Number",
            'aria-label="Rule-relevant details"',
        )

        assert all(element in card for element in required_elements)
        assert tuple(card.index(element) for element in required_elements) == (
            *sorted(card.index(element) for element in required_elements),
        )
        assert f"RECORD-{index:02d}" in card_text
        assert f"2026-07-24 10:{index:02d}" in card_text
        assert f"TRUCK-{index:02d}" in card_text
        assert f"EXCEPTION-MESSAGE-{index:02d}" in card_text
        assert rule_id not in card_text
        assert "Rule ID" not in card_text
        assert "CSV row" not in card_text
        assert f'data-rule-id="{rule_id}"' in card
        assert f'data-source-row-number="{index + 1}"' in card

        if rule_id == "CC-RULE-002":
            assert card_text.index("Record ID") < card_text.index(
                "Application Date"
            ) < card_text.index("Entry Date")
        else:
            assert "Application Date" not in card_text

        detail_labels = _DETAIL_LABELS_BY_RULE[rule_id]
        displayed_labels = _DISPLAY_DETAIL_LABELS_BY_RULE[rule_id]
        for detail_index, label in enumerate(detail_labels, start=1):
            detail_value = f"DETAIL-{index:02d}-{detail_index:02d}"
            if rule_id == "CC-RULE-002":
                assert label not in card_text
                continue
            if rule_id == "CC-RULE-004":
                if label == "Selected Type I fluid":
                    assert detail_value not in card_text
                elif label in {
                    "Recorded concentration",
                    "Outside air temperature",
                    "Authoritative manufacturer-chart freeze point",
                    "Actual calculated buffer",
                }:
                    assert detail_value in card_text
                else:
                    assert detail_value not in card_text
                assert label not in card_text
                continue
            if label in displayed_labels:
                assert label in card_text
                assert detail_value in card_text
            else:
                assert label not in card_text
                assert detail_value not in card_text

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
            if (
                rule_id == "CC-RULE-002"
                and omitted_value == f"OMIT-APPLICATION-DATE-{index:02d}"
            ):
                continue
            assert omitted_value not in card_text

    assert "Select All" in html
    assert "Clear All" in html
    assert "Export Selected" in html
    assert "data-export-all" in html
    assert "Rules executed" not in html
    assert "Selected Type I fluid" not in html
    assert "Selected Type IV fluid" not in html


def test_rule_002_renders_only_concise_timeline_content(app):
    exception = replace(
        _exception("CC-RULE-002", 2),
        exception_message="Late entry.",
        application_date="1/1/2026",
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
    html = _render_results(app, (exception,))
    card = re.search(
        r'<article\s+class="exception-card".*?</article>',
        html,
        flags=re.DOTALL,
    ).group()
    visible_text = _visible_text(card)

    assert visible_text == (
        "Late entry. Record ID RECORD-02 Application Date 1/1/2026 "
        "Entry Date 1/2/2026 8:08 Truck Number TRUCK-02 "
        "2 hours, 57 minutes past the 24-hour threshold."
    )
    assert visible_text.count("Entry Date") == 1
    for omitted in (
        "Rule ID",
        "CSV row",
        "Configured threshold",
        "Actual delay",
        "Amount beyond the threshold",
    ):
        assert omitted not in visible_text


def test_rule_004_renders_only_four_renamed_details(app):
    exception = replace(
        _exception("CC-RULE-004", 4),
        exception_message="18 degree buffer not met.",
        details=(
            RuleDetail("Selected Type I fluid", "Cryotech Polar Plus LT"),
            RuleDetail("Recorded concentration", "65%"),
            RuleDetail("Outside air temperature", "-33°F"),
            RuleDetail(
                "Authoritative manufacturer-chart freeze point",
                "-50.0°F",
            ),
            RuleDetail("Actual calculated buffer", "17.0°F"),
            RuleDetail("Required buffer", "18.0°F"),
            RuleDetail("Amount short", "1.0°F"),
        ),
    )
    html = _render_results(app, (exception,))
    card = re.search(
        r'<article\s+class="exception-card".*?</article>',
        html,
        flags=re.DOTALL,
    ).group()
    visible_text = _visible_text(card)

    assert visible_text == (
        "18 degree buffer not met. Record ID RECORD-04 "
        "Entry Date 2026-07-24 10:04 Truck Number TRUCK-04 "
        "Recorded Concentration 65% OAT -33°F Correct Freeze Point -50.0°F "
        "Calculated Buffer 17.0°F"
    )
    for omitted in (
        "Selected Type I fluid",
        "Cryotech Polar Plus LT",
        "Required Buffer",
        "18.0°F",
        "Amount Short",
        "1.0°F",
        "Comparison",
        "Rule ID",
        "CSV row",
    ):
        assert omitted not in visible_text


def test_export_form_keeps_results_open_and_exposes_progress_feedback(app):
    html = _render_results(app, (_exception("CC-RULE-003", 3),))

    assert 'method="post"' in html
    assert 'target="_blank"' in html
    assert html.count('formtarget="_blank"') == 4
    assert html.count("data-export-feedback\n") == 2
    assert html.count("data-export-feedback-message") == 2
    assert "Preparing Excel" not in html


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
        r'<li\s+class="audit-warning-card".*?</li>',
        html,
        flags=re.DOTALL,
    )

    assert warning_card is not None
    warning_text = _visible_text(warning_card.group())
    assert "Record ID WARNING-RECORD" in warning_text
    assert "CSV row" not in warning_text
    assert "Rule ID" not in warning_text
    assert "CC-RULE-004" not in warning_text
    assert 'data-rule-id="CC-RULE-004"' in warning_card.group()
    assert 'data-source-row-number="8"' in warning_card.group()
    assert "Unable to evaluate AmbientTemp, Type1Used" in warning_text
    assert "Unable to evaluate this synthetic warning." in warning_text
    assert html.index("audit-warning-summary") < html.index(
        'id="exception-export-form"'
    )
    assert "data-exception-checkbox" not in warning_card.group()
