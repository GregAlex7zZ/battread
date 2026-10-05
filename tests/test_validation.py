# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for validation.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

import warnings
from collections.abc import Callable

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from battread import is_standardized
from battread.exceptions import IncompatibleDataError, NonMonotonicTimeError
from battread.validation import validate_standardized
from battread.warnings import MissingValueWarning


def canonical_frame(
    time: list[float],
    current: list[float] | None = None,
    voltage: list[float] | None = None,
) -> pd.DataFrame:
    """Build a small float64 canonical fixture for contract checks."""
    row_count = len(time)
    return pd.DataFrame(
        {
            "time_s": np.asarray(time, dtype=np.float64),
            "current_mA": np.asarray(
                current if current is not None else [1.0] * row_count,
                dtype=np.float64,
            ),
            "voltage_V": np.asarray(
                voltage if voltage is not None else [3.7] * row_count,
                dtype=np.float64,
            ),
        }
    )


def test_valid_complete_dataframe_is_standardized_without_mutation() -> None:
    """Verify that valid complete dataframe is standardized without mutation.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    dataframe = canonical_frame([0.0, 1.0, 1.0, 2.0])
    original = dataframe.copy(deep=True)
    validate_standardized(dataframe)
    assert is_standardized(dataframe)
    pdt.assert_frame_equal(dataframe, original)


def test_missing_values_are_retained_and_reported_structurally() -> None:
    """Verify that missing values are retained and reported structurally.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    dataframe = canonical_frame(
        [np.nan, 0.0, 1.0, np.nan],
        [np.nan, 1.0, np.nan, 2.0],
        [3.7, np.nan, np.nan, 3.6],
    )
    original = dataframe.copy(deep=True)

    with pytest.warns(MissingValueWarning) as captured:
        validate_standardized(dataframe)

    warning = captured[0].message
    assert isinstance(warning, MissingValueWarning)
    assert dict(warning.affected_counts) == {
        "time_s": 2,
        "current_mA": 2,
        "voltage_V": 2,
    }
    assert "time_s: 2 rows" in str(warning)
    assert is_standardized(dataframe)
    pdt.assert_frame_equal(dataframe, original)


def test_is_standardized_is_warning_free() -> None:
    """Verify that is standardized is warning free.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    dataframe = canonical_frame([0.0], [np.nan], [3.7])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert is_standardized(dataframe)


@pytest.mark.parametrize(
    "dataframe",
    [
        canonical_frame([]),
        canonical_frame([np.nan, np.nan]),
        canonical_frame([1.0, 2.0]),
        canonical_frame([0.0, np.inf]),
        canonical_frame([0.0], [np.inf]),
        canonical_frame([0.0], voltage=[-np.inf]),
        canonical_frame([0.0, np.nan, 2.0, np.nan, 1.0]),
    ],
)
def test_invalid_scientific_data_is_not_standardized(dataframe: pd.DataFrame) -> None:
    """Verify that invalid scientific data is not standardized.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    assert not is_standardized(dataframe)


def test_empty_and_all_missing_time_raise_incompatible_data() -> None:
    """Verify that empty and all missing time raise incompatible data.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError, match="at least one row"):
        validate_standardized(canonical_frame([]))
    with pytest.raises(IncompatibleDataError, match="at least one finite"):
        validate_standardized(canonical_frame([np.nan]))


@pytest.mark.parametrize("column", ["time_s", "current_mA", "voltage_V"])
@pytest.mark.parametrize("value", [np.inf, -np.inf])
def test_infinity_in_any_canonical_column_fails(column: str, value: float) -> None:
    """Verify that infinity in any canonical column fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    dataframe = canonical_frame([0.0])
    dataframe.loc[0, column] = value
    with pytest.raises(IncompatibleDataError, match="infinity"):
        validate_standardized(dataframe)


def test_nonzero_origin_fails_without_repair() -> None:
    """Verify that nonzero origin fails without repair.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    dataframe = canonical_frame([10.0, 11.0])
    original = dataframe.copy(deep=True)
    with pytest.raises(IncompatibleDataError, match="must be 0"):
        validate_standardized(dataframe)
    pdt.assert_frame_equal(dataframe, original)


def test_backward_time_across_nan_raises_specific_error() -> None:
    """Verify that backward time across nan raises specific error.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    dataframe = canonical_frame([0.0, 2.0, np.nan, 1.0])
    with pytest.raises(NonMonotonicTimeError, match="backwards"):
        validate_standardized(dataframe)


def reorder_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a reordered schema to test canonical column-order rejection."""
    return frame[["current_mA", "time_s", "voltage_V"]]


def add_source_column(frame: pd.DataFrame) -> pd.DataFrame:
    """Add vendor metadata to test rejection of noncanonical extra columns."""
    result = frame.copy()
    result["source"] = np.array([1.0], dtype=np.float64)
    return result


def remove_voltage(frame: pd.DataFrame) -> pd.DataFrame:
    """Remove a required measurement to test missing-column rejection."""
    return frame.drop(columns=["voltage_V"])


def use_float32_time(frame: pd.DataFrame) -> pd.DataFrame:
    """Reduce time precision to test the exact float64 validation contract."""
    result = frame.copy()
    result["time_s"] = pd.Series(frame["time_s"], dtype="float32")
    return result


def rename_time(frame: pd.DataFrame) -> pd.DataFrame:
    """Rename canonical time to test rejection of an incompatible schema."""
    return frame.rename(columns={"time_s": "Time"})


@pytest.mark.parametrize(
    "transform",
    [
        reorder_columns,
        add_source_column,
        remove_voltage,
        use_float32_time,
        rename_time,
    ],
)
def test_exact_schema_order_names_and_dtypes_are_required(
    transform: Callable[[pd.DataFrame], pd.DataFrame],
) -> None:
    """Verify that exact schema order names and dtypes are required.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    dataframe = canonical_frame([0.0])
    candidate = transform(dataframe)
    with pytest.raises(IncompatibleDataError):
        validate_standardized(candidate)
    assert not is_standardized(candidate)


def test_non_dataframe_is_not_standardized() -> None:
    """Verify that non dataframe is not standardized.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    assert not is_standardized({"time_s": [0.0]})


def test_validation_rejects_non_dataframe_with_domain_error() -> None:
    """Verify that validation rejects non dataframe with domain error.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError, match="pandas DataFrame"):
        validate_standardized({"time_s": [0.0]})
