# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for labels.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

from dataclasses import FrozenInstanceError

import pytest

from battread.normalization.units import identify_unit, known_unit_aliases
from battread.recognition import ColumnMatch, normalize_label, parse_label


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("  Elapsed_Time  ", "elapsed time"),
        ("HALF-CYCLE.Time", "half cycle time"),
        ("I_cell", "i cell"),
        ("µCurrent", "μcurrent"),
    ],
)
def test_normalize_label(source: str, expected: str) -> None:
    """Verify that normalize label.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    assert normalize_label(source) == expected


@pytest.mark.parametrize(
    ("source", "label", "unit", "quantity", "canonical"),
    [
        ("Current (mA)", "current", "mA", "current", "mA"),
        ("Current [mA]", "current", "mA", "current", "mA"),
        ("Current/mA", "current", "mA", "current", "mA"),
        ("Current mA", "current", "mA", "current", "mA"),
        ("I/mA", "i", "mA", "current", "mA"),
        ("Capacity(Ah)", "capacity", "Ah", "capacity", "Ah"),
        ("Time/s", "time", "s", "time", "s"),
    ],
)
def test_supported_unit_locations(
    source: str,
    label: str,
    unit: str,
    quantity: str,
    canonical: str,
) -> None:
    """Verify that supported unit locations.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    parsed = parse_label(source)
    assert parsed.normalized_label == label
    assert parsed.unit_expression == unit
    assert parsed.unit_quantity == quantity
    assert parsed.canonical_unit == canonical


@pytest.mark.parametrize("alias", known_unit_aliases())
def test_every_registered_unit_alias_is_identifiable(alias: str) -> None:
    """Verify that every registered unit alias is identifiable.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    assert identify_unit(alias) is not None


@pytest.mark.parametrize("source", ["Current (MA)", "Time (Ms)", "Voltage (mv)"])
def test_si_symbol_case_is_not_weakened(source: str) -> None:
    """Verify that si symbol case is not weakened.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    parsed = parse_label(source)
    assert parsed.unit_expression is not None
    assert parsed.unit_quantity is None
    assert parsed.canonical_unit is None


@pytest.mark.parametrize(
    "source",
    [
        "Current Density (mA/cm2)",
        "Current Density (A/m²)",
        "Specific Capacity (mAh/g)",
        "Areal Capacity (mAh/cm²)",
        "Capacity (Ah/L)",
        "Capacity (C/g)",
    ],
)
def test_derived_units_are_identified(source: str) -> None:
    """Verify that derived units are identified.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    parsed = parse_label(source)
    assert parsed.derived_unit
    assert parsed.canonical_unit is None


def test_date_slash_time_is_a_label_not_a_unit_expression() -> None:
    """Verify that date slash time is a label not a unit expression.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    parsed = parse_label("date/time")
    assert parsed.normalized_label == "date time"
    assert parsed.unit_expression is None


def test_empty_slash_prefix_is_not_treated_as_a_unit_bearing_header() -> None:
    """Verify that empty slash prefix is not treated as a unit bearing header.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    parsed = parse_label("/mA")
    assert parsed.unit_expression is None


def test_column_match_is_immutable() -> None:
    """Verify that column match is immutable.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = ColumnMatch("Time", 0, "time", None, None, None, "resolved", 0.75, ())
    with pytest.raises(FrozenInstanceError):
        match.state = "unresolved"  # type: ignore[misc]
