# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for merge.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from battread import is_standardized, merge
from battread._pandas import numpy_values
from battread.exceptions import IncompatibleDataError, NonMonotonicTimeError
from battread.warnings import MissingValueWarning


def canonical_frame(
    time: list[float],
    *,
    current: float = 1.0,
    voltage: float = 3.7,
    index: list[int] | None = None,
) -> pd.DataFrame:
    """Build a small float64 canonical fixture for contract checks."""
    return pd.DataFrame(
        {
            "time_s": np.asarray(time, dtype=np.float64),
            "current_mA": np.full(len(time), current, dtype=np.float64),
            "voltage_V": np.full(len(time), voltage, dtype=np.float64),
        },
        index=index,
    )


def test_merge_uses_preceding_final_positive_interval() -> None:
    """Verify that merge uses preceding final positive interval.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    first = canonical_frame([0.0, 10.0, 20.0, 30.0])
    second = canonical_frame([0.0, 5.0, 10.0, 15.0], current=2.0)
    result = merge([first, second])

    np.testing.assert_array_equal(
        numpy_values(result["time_s"]),
        [0.0, 10.0, 20.0, 30.0, 40.0, 45.0, 50.0, 55.0],
    )
    np.testing.assert_array_equal(
        numpy_values(result["current_mA"]),
        [1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 2.0],
    )
    assert is_standardized(result)


def test_merge_does_not_mutate_inputs() -> None:
    """Verify that merge does not mutate inputs.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    first = canonical_frame([0.0, 1.0])
    second = canonical_frame([0.0, 2.0])
    first_original = first.copy(deep=True)
    second_original = second.copy(deep=True)
    merge([first, second])
    pdt.assert_frame_equal(first, first_original)
    pdt.assert_frame_equal(second, second_original)


def test_single_dataset_returns_independent_canonical_copy() -> None:
    """Verify that single dataset returns independent canonical copy.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = canonical_frame([0.0, 1.0], index=[4, 8])
    result = merge([source])
    pdt.assert_frame_equal(result, source)
    result.loc[4, "current_mA"] = 99.0
    assert source.loc[4, "current_mA"] == 1.0


def test_single_preceding_point_uses_following_interval() -> None:
    """Verify that single preceding point uses following interval.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = merge([canonical_frame([0.0]), canonical_frame([0.0, 5.0, 10.0])])
    np.testing.assert_array_equal(result["time_s"], [0.0, 5.0, 10.0, 15.0])


def test_following_interval_search_skips_zero_duration_pair() -> None:
    """Verify that following interval search skips zero duration pair.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = merge([canonical_frame([0.0]), canonical_frame([0.0, 0.0, 5.0])])
    np.testing.assert_array_equal(result["time_s"], [0.0, 5.0, 5.0, 10.0])


def test_single_following_point_uses_preceding_interval() -> None:
    """Verify that single following point uses preceding interval.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = merge([canonical_frame([0.0, 5.0, 10.0]), canonical_frame([0.0])])
    np.testing.assert_array_equal(result["time_s"], [0.0, 5.0, 10.0, 15.0])


def test_two_single_point_datasets_fail() -> None:
    """Verify that two single point datasets fail.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError, match="positive interval"):
        merge([canonical_frame([0.0]), canonical_frame([0.0])])


def test_bridge_does_not_cross_missing_row() -> None:
    """Verify that bridge does not cross missing row.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    first = canonical_frame([0.0, np.nan, 10.0, 10.0])
    second = canonical_frame([0.0, 5.0])
    with pytest.warns(MissingValueWarning):
        result = merge([first, second])
    np.testing.assert_allclose(
        result["time_s"],
        [0.0, np.nan, 10.0, 10.0, 15.0, 20.0],
        equal_nan=True,
    )


def test_leading_and_trailing_missing_times_remain_in_place() -> None:
    """Verify that leading and trailing missing times remain in place.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    first = canonical_frame([np.nan, 0.0, 10.0, np.nan])
    second = canonical_frame([np.nan, 0.0, 5.0, np.nan])
    with pytest.warns(MissingValueWarning) as captured:
        result = merge([first, second])
    np.testing.assert_allclose(
        result["time_s"],
        [np.nan, 0.0, 10.0, np.nan, np.nan, 20.0, 25.0, np.nan],
        equal_nan=True,
    )
    warning = captured[0].message
    assert isinstance(warning, MissingValueWarning)
    assert warning.affected_counts["time_s"] == 4


def test_repeated_final_time_searches_back_for_positive_interval() -> None:
    """Verify that repeated final time searches back for positive interval.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = merge(
        [
            canonical_frame([0.0, 10.0, 10.0]),
            canonical_frame([0.0, 2.0]),
        ]
    )
    np.testing.assert_array_equal(
        result["time_s"],
        [0.0, 10.0, 10.0, 20.0, 22.0],
    )


def test_more_than_two_datasets_use_each_adjacent_source_pair() -> None:
    """Verify that more than two datasets use each adjacent source pair.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = merge(
        [
            canonical_frame([0.0, 10.0]),
            canonical_frame([0.0, 5.0]),
            canonical_frame([0.0, 2.0]),
        ]
    )
    np.testing.assert_array_equal(
        result["time_s"],
        [0.0, 10.0, 20.0, 25.0, 30.0, 32.0],
    )


def test_no_adjacent_positive_interval_fails() -> None:
    """Verify that no adjacent positive interval fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    first = canonical_frame([0.0, np.nan, 0.0])
    second = canonical_frame([0.0, np.nan, 0.0])
    with pytest.raises(IncompatibleDataError, match="positive interval"):
        merge([first, second])


def test_empty_collection_and_direct_dataframe_fail() -> None:
    """Verify that empty collection and direct dataframe fail.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError, match="at least one"):
        merge([])
    with pytest.raises(IncompatibleDataError, match="not one DataFrame"):
        merge(canonical_frame([0.0]))


def test_invalid_input_reports_its_position() -> None:
    """Verify that invalid input reports its position.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    invalid = canonical_frame([0.0])
    invalid["time_s"] = pd.Series(invalid["time_s"], dtype="float32")
    with pytest.raises(IncompatibleDataError, match="input 1"):
        merge([canonical_frame([0.0, 1.0]), invalid])


def test_non_monotonic_input_preserves_specific_exception() -> None:
    """Verify that non monotonic input preserves specific exception.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    invalid = canonical_frame([0.0, 2.0, 1.0])
    with pytest.raises(NonMonotonicTimeError, match="input 1"):
        merge([canonical_frame([0.0, 1.0]), invalid])


def test_non_dataframe_element_fails() -> None:
    """Verify that non dataframe element fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError, match="not a pandas DataFrame"):
        merge([canonical_frame([0.0]), "not-a-frame"])  # type: ignore[list-item]
