# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for engine.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

from dataclasses import FrozenInstanceError

import pytest

from battread.exceptions import AmbiguousColumnError, MissingColumnError
from battread.recognition import (
    ReaderHint,
    inspection_result,
    recognize_columns,
    resolve_quantity,
)


@pytest.mark.parametrize(
    ("source", "quantity", "unit", "semantic"),
    [
        ("Time/s", "time", "s", None),
        ("Elapsed Time (s)", "time", "s", None),
        ("Current (mA)", "current", "mA", None),
        ("I/mA", "current", "mA", None),
        ("Voltage (V)", "voltage", "V", None),
        ("Potential/V", "voltage", "V", None),
        ("Charge Capacity", "capacity", None, "charge_capacity"),
        ("Discharge Capacity", "capacity", None, "discharge_capacity"),
        ("Capacity (mAh)", "capacity", "mAh", "generic_capacity"),
    ],
)
def test_acceptance_positive_examples(
    source: str, quantity: str, unit: str | None, semantic: str | None
) -> None:
    """Verify that acceptance positive examples.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns([source])[0]
    assert (match.quantity, match.unit, match.semantic, match.state) == (
        quantity,
        unit,
        semantic,
        "resolved",
    )


@pytest.mark.parametrize(
    ("source", "quantity"),
    [
        ("Step Time", "time"),
        ("Current Range", "current"),
        ("Current Limit", "current"),
        ("Current Density", "current"),
        ("Voltage Limit", "voltage"),
        ("Target Voltage", "voltage"),
        ("Specific Capacity", "capacity"),
        ("Applied Current", "current"),
        ("Applied Current (mA)", "current"),
    ],
)
def test_acceptance_negative_examples(source: str, quantity: str) -> None:
    """Verify that acceptance negative examples.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns([source])[0]
    assert match.quantity == quantity
    assert match.state == "unresolved"


def test_compatible_unit_strengthens_a_scientific_symbol() -> None:
    """Verify that compatible unit strengthens a scientific symbol.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    bare, unit_bearing = (
        recognize_columns(["I", "Other"])[0],
        recognize_columns(["I/mA"])[0],
    )
    assert bare.state == "unresolved"
    assert unit_bearing.state == "resolved"
    assert unit_bearing.confidence > bare.confidence


def test_incompatible_unit_rejects_an_exact_alias() -> None:
    """Verify that incompatible unit rejects an exact alias.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns(["Current (V)"])[0]
    assert match.quantity == "current"
    assert match.state == "unresolved"
    assert any("incompatible" in evidence for evidence in match.evidence)


def test_unregistered_unit_is_explained_without_case_folding() -> None:
    """Verify that unregistered unit is explained without case folding.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns(["Current (MA)"])[0]
    assert match.state == "resolved"
    assert match.unit is None
    assert any("not registered" in evidence for evidence in match.evidence)


def test_unit_evidence_alone_does_not_resolve_a_quantity() -> None:
    """Verify that unit evidence alone does not resolve a quantity.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns(["Reading (mA)"])[0]
    assert match.quantity == "current"
    assert match.state == "unresolved"


def test_unknown_header_remains_inspectable() -> None:
    """Verify that unknown header remains inspectable.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns(["Operator note"])[0]
    assert match.quantity == "unknown"
    assert match.state == "unresolved"
    assert match.source_position == 0


def test_canonical_names_are_authoritative() -> None:
    """Verify that canonical names are authoritative.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    matches = recognize_columns(["time_s", "current_mA", "voltage_V"])
    assert [match.quantity for match in matches] == ["time", "current", "voltage"]
    assert [match.unit for match in matches] == ["s", "mA", "V"]
    assert all(match.state == "resolved" for match in matches)
    assert all("canonical" in match.evidence[0] for match in matches)


def test_elapsed_time_outranks_absolute_time() -> None:
    """Verify that elapsed time outranks absolute time.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    absolute, elapsed = recognize_columns(["Timestamp", "Elapsed Time (s)"])
    assert absolute.state == "unresolved"
    assert elapsed.state == "resolved"


def test_multiple_measured_potentials_are_ambiguous() -> None:
    """Verify that multiple measured potentials are ambiguous.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    matches = recognize_columns(["Cell Voltage (V)", "Reference Voltage (V)"])
    assert [match.state for match in matches] == ["ambiguous", "ambiguous"]
    with pytest.raises(AmbiguousColumnError, match="position 0"):
        resolve_quantity(matches, "voltage")


def test_numbered_currents_are_ambiguous_and_order_independent() -> None:
    """Verify that numbered currents are ambiguous and order independent.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    forward = recognize_columns(["Current 1 (mA)", "Current 2 (mA)"])
    reverse = recognize_columns(["Current 2 (mA)", "Current 1 (mA)"])
    assert all(match.state == "ambiguous" for match in (*forward, *reverse))
    assert {match.confidence for match in forward} == {
        match.confidence for match in reverse
    }


def test_duplicate_labels_preserve_positions_and_are_ambiguous() -> None:
    """Verify that duplicate labels preserve positions and are ambiguous.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    matches = recognize_columns(["Current (mA)", "Current (mA)"])
    assert [match.source_position for match in matches] == [0, 1]
    assert all(match.state == "ambiguous" for match in matches)


def test_stronger_current_alias_wins_without_using_column_order() -> None:
    """Verify that stronger current alias wins without using column order.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    first = recognize_columns(["I/mA", "Measured Current (mA)"])
    second = recognize_columns(["Measured Current (mA)", "I/mA"])
    assert resolve_quantity(first, "current").source_column == "Measured Current (mA)"
    assert resolve_quantity(second, "current").source_column == "Measured Current (mA)"


def test_charge_discharge_pair_is_not_treated_as_competing_capacity() -> None:
    """Verify that charge discharge pair is not treated as competing capacity.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    matches = recognize_columns(["Charge Capacity (mAh)", "Discharge Capacity (mAh)"])
    assert [match.semantic for match in matches] == [
        "charge_capacity",
        "discharge_capacity",
    ]
    assert all(match.state == "resolved" for match in matches)
    assert (
        resolve_quantity(
            matches, "capacity", semantic="charge_capacity"
        ).source_position
        == 0
    )


def test_generic_delta_capacity_does_not_invent_alignment_or_signed_semantics() -> None:
    """Verify that generic delta capacity does not invent alignment or signed semantics.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    match = recognize_columns(["dQ (mAh)"])[0]
    assert match.state == "resolved"
    assert match.semantic == "unknown_capacity"
    assert match.interval_alignment is None


def test_biologic_overlay_is_scoped_and_conservative() -> None:
    """Verify that biologic overlay is scoped and conservative.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    generic = recognize_columns(["Ewe/V", "dq/mA.h"])
    biologic = recognize_columns(["Ewe/V", "dq/mA.h"], vendor="biologic")
    assert generic[0].state == "unresolved"
    assert biologic[0].quantity == "voltage"
    assert biologic[0].state == "resolved"
    assert biologic[1].semantic == "unknown_capacity"
    assert biologic[1].interval_alignment is None


def test_neware_overlay_does_not_guess_textual_schema() -> None:
    """Verify that neware overlay does not guess textual schema.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    assert recognize_columns(["Neware magic current"], vendor="neware")[0].state == (
        "unresolved"
    )


def test_authoritative_hint_can_resolve_applied_current() -> None:
    """Verify that authoritative hint can resolve applied current.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    hint = ReaderHint("Applied Current (mA)", "current", unit="mA")
    match = recognize_columns(["Applied Current (mA)"], hints=[hint])[0]
    assert match.state == "resolved"
    assert match.confidence == 1.0
    assert match.unit == "mA"


def test_authoritative_hint_may_leave_unit_for_a_later_override() -> None:
    """Verify that authoritative hint may leave unit for a later override.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    hint = ReaderHint("Vendor clock", "time")
    match = recognize_columns(["Vendor clock"], hints=[hint])[0]
    assert match.state == "resolved"
    assert match.unit is None


def test_authoritative_hint_carries_capacity_alignment() -> None:
    """Verify that authoritative hint carries capacity alignment.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    hint = ReaderHint(
        "dq/mA.h",
        "capacity",
        unit="mAh",
        semantic="delta_signed",
        interval_alignment="previous",
    )
    match = recognize_columns(["dq/mA.h"], hints=[hint])[0]
    assert match.semantic == "delta_signed"
    assert match.interval_alignment == "previous"


def test_positional_hint_distinguishes_duplicate_names() -> None:
    """Verify that positional hint distinguishes duplicate names.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    hint = ReaderHint("Current", "current", unit="mA", source_position=1)
    matches = recognize_columns(["Current", "Current"], hints=[hint])
    assert matches[1].confidence == 1.0
    assert matches[1].state == "resolved"
    assert matches[0].state == "unresolved"


def test_resolve_quantity_reports_missing_quantity() -> None:
    """Verify that resolve quantity reports missing quantity.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(MissingColumnError, match="No resolved voltage"):
        resolve_quantity(recognize_columns(["Time/s"]), "voltage")


def test_inspection_result_reports_direct_current_precedence() -> None:
    """Verify that inspection result reports direct current precedence.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = inspection_result(
        format="csv",
        reader="delimited",
        columns=["Time/s", "Current (mA)", "Capacity (mAh)", "Voltage (V)"],
        delimiter=",",
        decimal_separator=".",
        encoding="utf-8",
    )
    assert result.current_reconstruction_required is False
    assert result.delimiter == ","
    with pytest.raises(FrozenInstanceError):
        result.reader = "other"  # type: ignore[misc]


def test_generic_capacity_does_not_claim_reconstruction_is_possible() -> None:
    """Verify that generic capacity does not claim reconstruction is possible.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = inspection_result(
        format="csv", reader="delimited", columns=["Capacity (mAh)"]
    )
    assert result.current_reconstruction_required is None


def test_current_without_known_unit_does_not_claim_direct_use() -> None:
    """Verify that current without known unit does not claim direct use.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = inspection_result(format="csv", reader="delimited", columns=["Current"])
    assert result.current_reconstruction_required is None


def test_capacity_pair_without_known_units_does_not_claim_reconstruction() -> None:
    """Verify that capacity pair without known units does not claim reconstruction.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = inspection_result(
        format="csv",
        reader="delimited",
        columns=["Charge Capacity", "Discharge Capacity"],
    )
    assert result.current_reconstruction_required is None


def test_safe_capacity_pair_marks_reconstruction_as_required() -> None:
    """Verify that safe capacity pair marks reconstruction as required.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = inspection_result(
        format="csv",
        reader="delimited",
        columns=["Charge Capacity (mAh)", "Discharge Capacity (mAh)"],
    )
    assert result.current_reconstruction_required is True


def test_ambiguous_current_keeps_reconstruction_strategy_unknown() -> None:
    """Verify that ambiguous current keeps reconstruction strategy unknown.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = inspection_result(
        format="csv",
        reader="delimited",
        columns=["Current 1 (mA)", "Current 2 (mA)", "Capacity (mAh)"],
    )
    assert result.current_reconstruction_required is None
