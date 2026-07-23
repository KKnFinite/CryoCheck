"""Coverage for the read-only CryoCheck rules catalog."""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from app.services.rules import IMPLEMENTATION_STATUS, RULES, RuleDefinition


EXPECTED_RULE_IDS = tuple(f"CC-RULE-{number:03d}" for number in range(1, 12))
EXPECTED_EXCEPTION_MESSAGES = (
    "Application entry proceeds event.",
    "Late entry.",
    "Incorrect freeze point.",
    "18 degree buffer not met.",
    "BRIX out of range.",
    "Excessive gap between steps.",
    "No Type IV during active precipitation.",
    "Excessive Type I.",
    "Excessive Type IV.",
    "Excessive event time.",
    "Incorrect Type IV concentration.",
)


def test_rules_page_returns_200_with_documented_count(client):
    response = client.get("/rules")

    assert response.status_code == 200
    assert b"CryoCheck Rules" in response.data
    assert b"11 documented rules" in response.data


def test_rule_ids_are_unique_and_in_permanent_numeric_order():
    rule_ids = tuple(rule.rule_id for rule in RULES)

    assert rule_ids == EXPECTED_RULE_IDS
    assert len(rule_ids) == len(set(rule_ids))


def test_each_rule_has_one_rule_id_label_in_order(client):
    page = client.get("/rules").get_data(as_text=True)
    displayed_ids = re.findall(
        r'<p class="rule-card__id">(CC-RULE-\d{3})</p>',
        page,
    )

    assert tuple(displayed_ids) == EXPECTED_RULE_IDS


def test_registry_is_immutable_and_has_no_category_field():
    definition_fields = {field.name for field in fields(RuleDefinition)}

    assert "category" not in definition_fields
    assert isinstance(RULES, tuple)
    with pytest.raises(FrozenInstanceError):
        RULES[0].name = "Changed"  # type: ignore[misc]


def test_rules_page_has_no_category_headings(client):
    page = client.get("/rules").get_data(as_text=True)

    assert re.search(r"<h[1-6][^>]*>\s*categor(?:y|ies)\s*</h[1-6]>", page, re.I) is None


def test_exact_exception_messages_appear(client):
    page = client.get("/rules").get_data(as_text=True)

    assert tuple(rule.exception_message for rule in RULES) == (
        EXPECTED_EXCEPTION_MESSAGES
    )
    for message in EXPECTED_EXCEPTION_MESSAGES:
        assert page.count(message) == 1


def test_every_rule_is_marked_implementation_pending(client):
    page = client.get("/rules").get_data(as_text=True)

    assert IMPLEMENTATION_STATUS == "Documented — implementation pending"
    assert page.count(IMPLEMENTATION_STATUS) == len(RULES)
    assert "not executed during CSV import" in page


def test_import_and_rules_navigation_active_states(client):
    import_page = client.get("/").get_data(as_text=True)
    rules_page = client.get("/rules").get_data(as_text=True)

    assert re.search(
        r'class="site-nav__link site-nav__link--active"[^>]*'
        r'href="/"[^>]*aria-current="page"[^>]*>\s*Import\s*</a>',
        import_page,
    )
    assert not re.search(
        r'href="/rules"[^>]*aria-current="page"',
        import_page,
    )
    assert re.search(
        r'class="site-nav__link site-nav__link--active"[^>]*'
        r'href="/rules"[^>]*aria-current="page"[^>]*>\s*Rules\s*</a>',
        rules_page,
    )
    assert not re.search(
        r'href="/"[^>]*aria-current="page"',
        rules_page,
    )


def test_rules_documentation_stays_synchronized_with_registry():
    documentation = Path("docs/rules.md").read_text(encoding="utf-8")
    normalized_documentation = " ".join(documentation.split())

    for rule in RULES:
        assert f"## {rule.rule_id} — {rule.name}" in documentation
        assert f"`{rule.exception_message}`" in documentation
        for detail in (
            *rule.logic_summary,
            *rule.settings_defaults,
            *rule.output_details,
        ):
            assert " ".join(detail.split()) in normalized_documentation

    assert "documented but not executed yet" in normalized_documentation
    assert "must remain synchronized" in normalized_documentation
    assert "Rule IDs are permanent" in normalized_documentation
    assert "No rule categories are used" in normalized_documentation
    assert "Rules are mandatory" in normalized_documentation
