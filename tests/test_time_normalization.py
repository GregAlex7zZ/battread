# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for time normalization.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

import numpy as np
import pytest

from battread.exceptions import IncompatibleDataError, NonMonotonicTimeError
from battread.normalization import normalize_time


def test_time_is_shifted_by_first_finite_value_without_mutation() -> None:
    """Verify that time is shifted by first finite value without mutation.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = np.array([100.0, 101.0, 102.0])
    result = normalize_time(source)
    np.testing.assert_array_equal(result, [0.0, 1.0, 2.0])
    np.testing.assert_array_equal(source, [100.0, 101.0, 102.0])


def test_missing_rows_and_duplicate_times_are_preserved() -> None:
    """Verify that missing rows and duplicate times are preserved.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = normalize_time([np.nan, 10.0, 10.0, 12.0, np.nan])
    np.testing.assert_allclose(
        result,
        [np.nan, 0.0, 0.0, 2.0, np.nan],
        equal_nan=True,
    )


def test_time_monotonicity_is_checked_across_missing_rows() -> None:
    """Verify that time monotonicity is checked across missing rows.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(NonMonotonicTimeError, match="backwards"):
        normalize_time([0.0, np.nan, 2.0, np.nan, 1.0])


@pytest.mark.parametrize(
    "values",
    [
        [],
        [np.nan, np.nan],
        [0.0, np.inf],
        [0.0, -np.inf],
        [[0.0, 1.0]],
        ["bad"],
    ],
)
def test_invalid_time_input_fails(values: object) -> None:
    """Verify that invalid time input fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError):
        normalize_time(values)
