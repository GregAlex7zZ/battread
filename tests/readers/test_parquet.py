# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for parquet.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

# PyArrow does not publish complete type information for its Python boundary.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import math
import warnings
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from battread import detect_format, inspect, iter_read, read, write
from battread.exceptions import (
    CorruptedFileError,
    IncompatibleDataError,
    NonMonotonicTimeError,
)
from battread.warnings import MissingValueWarning


def _frame(dtype: str = "float64") -> pd.DataFrame:
    """Build deterministic canonical measurements for round-trip comparisons."""
    return pd.DataFrame(
        {
            "time_s": pd.Series([0.0, 1.0, 2.0], dtype=dtype),
            "current_mA": pd.Series([1.0, -2.0, 3.0], dtype=dtype),
            "voltage_V": pd.Series([3.0, 3.1, 3.2], dtype=dtype),
        }
    )


def test_canonical_parquet_detection_inspection_and_read(tmp_path: Path) -> None:
    """Verify that canonical parquet detection inspection and read.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = write(_frame(), tmp_path / "data.parquet")
    detected = detect_format(source)
    information = inspect(source)
    result = read(source)

    assert detected.format == "parquet"
    assert detected.reader == "parquet"
    assert detected.confidence == 1.0
    assert information.reader == "parquet"
    assert information.current_reconstruction_required is False
    assert all(match.state == "resolved" for match in information.columns)
    pd.testing.assert_frame_equal(result, _frame())


def test_parquet_magic_overrides_wrong_extension(tmp_path: Path) -> None:
    """Verify that parquet magic overrides wrong extension.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = write(_frame(), tmp_path / "data.csv", format="parquet")
    assert detect_format(source).format == "parquet"
    pd.testing.assert_frame_equal(read(source), _frame())


def test_float32_parquet_becomes_float64(tmp_path: Path) -> None:
    """Verify that float32 parquet becomes float64.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "float32.parquet"
    pq.write_table(pa.Table.from_pandas(_frame("float32")), source)
    result = read(source)
    assert result.dtypes.tolist() == [np.dtype("float64")] * 3
    np.testing.assert_allclose(result.to_numpy(), _frame().to_numpy())


@pytest.mark.parametrize("chunk_size", [1, 2, 10])
def test_parquet_chunks_equal_complete_read(tmp_path: Path, chunk_size: int) -> None:
    """Verify that parquet chunks equal complete read.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = write(_frame(), tmp_path / "chunks.parquet")
    complete = read(source)
    chunks = list(iter_read(source, chunk_size=chunk_size))
    assert all(len(chunk) <= chunk_size for chunk in chunks)
    pd.testing.assert_frame_equal(pd.concat(chunks, ignore_index=True), complete)


def test_parquet_missing_values_are_preserved_and_warned(tmp_path: Path) -> None:
    """Verify that parquet missing values are preserved and warned.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    dataframe = _frame()
    dataframe.loc[1, "current_mA"] = np.nan
    with pytest.warns(MissingValueWarning):
        source = write(dataframe, tmp_path / "missing.parquet")
    with pytest.warns(MissingValueWarning):
        result = read(source)
    assert math.isnan(cast(float, result.loc[1, "current_mA"]))


def test_invalid_parquet_schema_is_rejected(tmp_path: Path) -> None:
    """Verify that invalid parquet schema is rejected.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    extra = _frame().assign(extra=1.0)
    source = tmp_path / "extra.parquet"
    pq.write_table(pa.Table.from_pandas(extra, preserve_index=False), source)
    with pytest.raises(IncompatibleDataError, match="columns must be exactly"):
        inspect(source)


def test_corrupt_parquet_with_magic_is_reported(tmp_path: Path) -> None:
    """Verify that corrupt parquet with magic is reported.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "corrupt.parquet"
    source.write_bytes(b"PAR1brokenPAR1")
    assert detect_format(source).reader == "parquet"
    with pytest.raises(CorruptedFileError, match="Invalid Parquet"):
        inspect(source)


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("sep", ","),
        ("decimal", "."),
        ("encoding", "utf-8"),
        ("header", None),
        ("skiprows", 1),
        ("autodetect", False),
        ("columns", {"time": 0}),
        ("units", {"time": "s"}),
        ("capacity_interval", "previous"),
    ],
)
def test_parquet_rejects_irrelevant_reader_options(
    tmp_path: Path, keyword: str, value: object
) -> None:
    """Verify that parquet rejects irrelevant reader options.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = write(_frame(), tmp_path / "options.parquet")
    with pytest.raises(IncompatibleDataError):
        read(source, **{keyword: value})  # type: ignore[arg-type]


def test_parquet_stream_validation_crosses_batches(tmp_path: Path) -> None:
    """Verify that parquet stream validation crosses batches.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "backward.parquet"
    dataframe = _frame()
    dataframe["time_s"] = [0.0, 2.0, 1.0]
    pq.write_table(pa.Table.from_pandas(dataframe, preserve_index=False), source)
    iterator = iter_read(source, chunk_size=2)
    assert len(next(iterator)) == 2
    with pytest.raises(NonMonotonicTimeError):
        next(iterator)


def test_empty_and_all_missing_time_parquet_fail(tmp_path: Path) -> None:
    """Verify that empty and all missing time parquet fail.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    empty = _frame().iloc[:0]
    empty_path = tmp_path / "empty.parquet"
    pq.write_table(pa.Table.from_pandas(empty, preserve_index=False), empty_path)
    with pytest.raises(IncompatibleDataError, match="at least one row"):
        read(empty_path)
    with pytest.raises(IncompatibleDataError, match="at least one row"):
        list(iter_read(empty_path))

    missing = _frame()
    missing["time_s"] = np.nan
    missing_path = tmp_path / "missing-time.parquet"
    pq.write_table(pa.Table.from_pandas(missing, preserve_index=False), missing_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingValueWarning)
        with pytest.raises(IncompatibleDataError, match="finite value"):
            read(missing_path)
