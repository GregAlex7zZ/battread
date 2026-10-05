# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for units.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

import numpy as np
import pytest

from battread.exceptions import (
    IncompatibleDataError,
    InvalidUnitError,
    UnknownUnitError,
)
from battread.normalization.units import (
    Quantity,
    canonical_unit,
    conversion_factor,
    convert_to_canonical,
)


@pytest.mark.parametrize(
    ("quantity", "unit", "source", "expected"),
    [
        ("time", "ms", [1000.0], [1.0]),
        ("time", "min", [2.0], [120.0]),
        ("time", "h", [2.0], [7200.0]),
        ("time", "day", [2.0], [172800.0]),
        ("current", "A", [1.5], [1500.0]),
        ("current", "µA", [1000.0], [1.0]),
        ("current", "μA", [1000.0], [1.0]),
        ("current", "nA", [1_000_000.0], [1.0]),
        ("voltage", "mV", [3700.0], [3.7]),
        ("voltage", "µV", [1_000_000.0], [1.0]),
        ("capacity", "Ah", [1.0], [1000.0]),
        ("capacity", "C", [3.6], [1.0]),
        ("capacity", "µAh", [1000.0], [1.0]),
    ],
)
def test_convert_to_canonical(
    quantity: Quantity,
    unit: str,
    source: list[float],
    expected: list[float],
) -> None:
    """Verify that convert to canonical.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = convert_to_canonical(source, quantity=quantity, unit=unit)
    np.testing.assert_allclose(result, expected)
    assert result.dtype == np.dtype(np.float64)


def test_conversion_returns_independent_array() -> None:
    """Verify that conversion returns independent array.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = np.array([1.0], dtype=np.float64)
    result = convert_to_canonical(source, quantity="current", unit="mA")
    result[0] = 4.0
    assert source[0] == 1.0


@pytest.mark.parametrize(("quantity", "unit"), [("current", "MA"), ("time", "Ms")])
def test_si_prefix_case_is_not_folded(quantity: Quantity, unit: str) -> None:
    """Verify that si prefix case is not folded.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(UnknownUnitError, match="Unknown"):
        conversion_factor(quantity, unit)


def test_known_but_dimensionally_incompatible_unit_fails() -> None:
    """Verify that known but dimensionally incompatible unit fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(InvalidUnitError, match="incompatible"):
        conversion_factor("current", "V")


def test_non_numeric_values_fail_with_domain_error() -> None:
    """Verify that non numeric values fail with domain error.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError, match="numerically compatible"):
        convert_to_canonical(["not-a-number"], quantity="voltage", unit="V")


def test_canonical_units_are_exposed_for_internal_pipeline() -> None:
    """Verify that canonical units are exposed for internal pipeline.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    assert canonical_unit("time") == "s"
    assert canonical_unit("current") == "mA"
    assert canonical_unit("voltage") == "V"
    assert canonical_unit("capacity") == "mAh"
