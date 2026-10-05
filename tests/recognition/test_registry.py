# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for registry.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

import pytest

from battread.recognition import recognize_columns
from battread.recognition.registry import (
    CAPACITY_EXCLUSIONS,
    CURRENT_NEGATIVE_TERMS,
    GENERIC_RULES,
    TIME_EXCLUSIONS,
    VOLTAGE_NEGATIVE_TERMS,
)


@pytest.mark.parametrize(
    ("quantity", "alias", "semantic", "should_resolve"),
    [
        (rule.quantity, alias, rule.semantic, rule.evidence_class != "weak")
        for rule in GENERIC_RULES
        for alias in rule.aliases
    ],
)
def test_every_generic_alias_has_a_recognition_test(
    quantity: str,
    alias: str,
    semantic: str | None,
    should_resolve: bool,
) -> None:
    """Verify that every generic alias has a recognition test.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns([alias])[0]
    assert match.quantity == quantity
    assert match.semantic == semantic
    assert (match.state == "resolved") is should_resolve


@pytest.mark.parametrize("alias", TIME_EXCLUSIONS)
def test_every_time_exclusion_is_rejected(alias: str) -> None:
    """Verify that every time exclusion is rejected.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns([alias])[0]
    assert match.quantity == "time"
    assert match.state == "unresolved"
    assert match.confidence == 0.0


@pytest.mark.parametrize("term", CURRENT_NEGATIVE_TERMS)
def test_every_current_negative_term_is_rejected(term: str) -> None:
    """Verify that every current negative term is rejected.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns([f"Current {term} (mA)"])[0]
    assert match.quantity == "current"
    assert match.state == "unresolved"


@pytest.mark.parametrize("term", VOLTAGE_NEGATIVE_TERMS)
def test_every_voltage_negative_term_is_rejected(term: str) -> None:
    """Verify that every voltage negative term is rejected.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns([f"Voltage {term} (V)"])[0]
    assert match.quantity == "voltage"
    assert match.state == "unresolved"


@pytest.mark.parametrize("alias", CAPACITY_EXCLUSIONS)
def test_every_capacity_exclusion_is_rejected(alias: str) -> None:
    """Verify that every capacity exclusion is rejected.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns([f"{alias} (mAh)"])[0]
    assert match.quantity == "capacity"
    assert match.state == "unresolved"


@pytest.mark.parametrize(
    "source",
    [
        "Current Density (mA/cm2)",
        "Specific Capacity (mAh/g)",
        "Charge Capacity (Ah/kg)",
    ],
)
def test_derived_quantities_are_rejected(source: str) -> None:
    """Verify that derived quantities are rejected.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns([source])[0]
    assert match.state == "unresolved"
    assert any("derived" in evidence for evidence in match.evidence)
