# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for large streaming.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

import warnings
from pathlib import Path
from typing import Protocol, cast

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from battread import convert, iter_read, read
from battread.exceptions import NonMonotonicTimeError
from battread.normalization import normalize_time
from battread.warnings import MissingValueWarning


class _IntegerGenerator(Protocol):
    """Type the exact RNG call used by the independent scalar-reference fixture."""

    def integers(self, low: int, high: int, size: int) -> NDArray[np.int64]:
        """Generate the requested number of int64 steps in the half-open range."""
        ...


def test_vector_time_matches_scalar_reference() -> None:
    """Verify that vector time matches scalar reference.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    random = np.random.default_rng(42)
    # NumPy 1.26's overloads are incomplete under strict Pyright. Describe this
    # exact three-argument call without changing the RNG or generated integers.
    draw = cast(_IntegerGenerator, random).integers
    source = draw(0, 4, 20_003).cumsum().astype(np.float64)
    source[random.random(source.size) < 0.2] = np.nan
    finite = [float(value) for value in source if not np.isnan(value)]
    expected = np.array([value - finite[0] for value in source])
    actual = normalize_time(source)
    np.testing.assert_array_equal(actual, expected)
    source[-1] = finite[-1] - 10
    with pytest.raises(NonMonotonicTimeError):
        normalize_time(source)


@pytest.mark.parametrize("chunk_size", [7, 1000, 10_000])
def test_large_streaming_retains_missing_rows_and_exact_values(
    tmp_path: Path, chunk_size: int
) -> None:
    """Verify that large streaming retains missing rows and exact values.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "source.csv"
    target = tmp_path / "target.parquet"
    times = np.arange(20_003, dtype=np.float64) + 100
    times[:11] = np.nan
    times[995:1005] = np.nan
    expected = pd.DataFrame(
        {
            "time_s": times - 111,
            "current_mA": np.full(times.size, -2.5),
            "voltage_V": np.full(times.size, 3.25),
        }
    )
    original = expected.rename(
        columns={
            "time_s": "time/s",
            "current_mA": "Current(mA)",
            "voltage_V": "Voltage(V)",
        }
    )
    original["time/s"] = times
    original.to_csv(source, index=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingValueWarning)
        actual = pd.concat(iter_read(source, chunk_size=chunk_size), ignore_index=True)
        convert(source, target, chunk_size=chunk_size)
        parquet = read(target)
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)
    pd.testing.assert_frame_equal(parquet, expected, check_exact=True)
