# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for output.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

# PyArrow does not publish complete type information for its Python boundary.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import math
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

import battread.output as output_module
from battread import convert, read, write
from battread.exceptions import (
    CorruptedFileError,
    IncompatibleDataError,
    NonMonotonicTimeError,
    OutputExistsError,
    UnsupportedFormatError,
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


@pytest.mark.parametrize("format", ["parquet", "csv", "txt"])
def test_write_round_trip_all_formats(tmp_path: Path, format: str) -> None:
    """Verify that write round trip all formats.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    destination = tmp_path / f"data.{format}"
    result = write(_frame(), destination)
    assert result == destination
    pd.testing.assert_frame_equal(read(destination), _frame())


def test_reference_text_output_dialects(tmp_path: Path) -> None:
    """Verify that reference text output dialects.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    csv_path = write(_frame(), tmp_path / "data.csv")
    txt_path = write(_frame(), tmp_path / "data.txt")

    csv_text = csv_path.read_text(encoding="utf-8")
    txt_text = txt_path.read_text(encoding="utf-8")
    assert csv_text.startswith("time_s,current_mA,voltage_V\n")
    assert txt_text.startswith("time_s\tcurrent_mA\tvoltage_V\n")
    assert "0,1,2" not in csv_text
    assert "," in csv_text and "\t" not in csv_text
    assert "\t" in txt_text


@pytest.mark.parametrize("dtype", ["float32", "int64"])
def test_write_converts_compatible_numeric_dtypes(tmp_path: Path, dtype: str) -> None:
    """Verify that write converts compatible numeric dtypes.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    dataframe = (
        _frame(dtype)
        if dtype == "float32"
        else pd.DataFrame(
            {"time_s": [0, 1, 2], "current_mA": [1, -2, 3], "voltage_V": [3, 4, 5]},
            dtype="int64",
        )
    )
    destination = write(dataframe, tmp_path / "converted.parquet")
    assert read(destination).dtypes.tolist() == [np.dtype("float64")] * 3
    assert dataframe.dtypes.tolist() == [np.dtype(dtype)] * 3


def test_write_accepts_numeric_compatible_strings(tmp_path: Path) -> None:
    """Verify that write accepts numeric compatible strings.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    dataframe = _frame().astype("string")
    destination = write(dataframe, tmp_path / "strings.csv")
    np.testing.assert_allclose(read(destination).to_numpy(), _frame().to_numpy())


@pytest.mark.parametrize(
    "dataframe",
    [
        _frame()[["current_mA", "time_s", "voltage_V"]],
        _frame().assign(extra=1.0),
        pd.DataFrame(columns=["time_s", "current_mA", "voltage_V"]),
    ],
)
def test_write_rejects_invalid_schema_or_empty_data(
    tmp_path: Path, dataframe: pd.DataFrame
) -> None:
    """Verify that write rejects invalid schema or empty data.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError):
        write(dataframe, tmp_path / "invalid.parquet")


def test_write_does_not_repair_time_or_numeric_content(tmp_path: Path) -> None:
    """Verify that write does not repair time or numeric content.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    nonzero = _frame()
    nonzero["time_s"] += 10.0
    with pytest.raises(IncompatibleDataError, match="must be 0"):
        write(nonzero, tmp_path / "nonzero.parquet")

    nonnumeric = _frame().astype(object)
    nonnumeric.loc[1, "current_mA"] = "bad"
    with pytest.raises(IncompatibleDataError, match="not compatible"):
        write(nonnumeric, tmp_path / "nonnumeric.parquet")


def test_write_preserves_and_warns_for_nan(tmp_path: Path) -> None:
    """Verify that write preserves and warns for nan.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    dataframe = _frame()
    dataframe.loc[1, "voltage_V"] = np.nan
    with pytest.warns(MissingValueWarning) as caught:
        destination = write(dataframe, tmp_path / "missing.csv")
    message = caught[0].message
    assert isinstance(message, MissingValueWarning)
    assert message.affected_counts == {"voltage_V": 1}
    with pytest.warns(MissingValueWarning):
        result = read(destination)
    assert math.isnan(cast(float, result.loc[1, "voltage_V"]))


def test_existing_destination_requires_overwrite(tmp_path: Path) -> None:
    """Verify that existing destination requires overwrite.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    destination = tmp_path / "data.csv"
    destination.write_bytes(b"original")
    with pytest.raises(OutputExistsError):
        write(_frame(), destination)
    assert destination.read_bytes() == b"original"

    assert write(_frame(), destination, overwrite=True) == destination
    pd.testing.assert_frame_equal(read(destination), _frame())


def test_explicit_format_overrides_extension(tmp_path: Path) -> None:
    """Verify that explicit format overrides extension.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    destination = write(_frame(), tmp_path / "data.bin", format="parquet")
    assert destination.read_bytes()[:4] == b"PAR1"
    pd.testing.assert_frame_equal(read(destination), _frame())


def test_unsupported_output_format_and_missing_parent_fail(tmp_path: Path) -> None:
    """Verify that unsupported output format and missing parent fail.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(UnsupportedFormatError, match="infer output format"):
        write(_frame(), tmp_path / "data.unknown")
    with pytest.raises(UnsupportedFormatError, match="Unsupported output"):
        write(_frame(), tmp_path / "data.bin", format="xlsx")  # type: ignore[arg-type]
    with pytest.raises(IncompatibleDataError, match="directory does not exist"):
        write(_frame(), tmp_path / "missing" / "data.csv")


def test_write_failure_cleans_temp_and_preserves_existing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that write failure cleans temp and preserves existing destination.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    destination = tmp_path / "data.csv"
    destination.write_bytes(b"original")

    def fail(dataframe: pd.DataFrame, path: Path, format: object) -> None:
        """Inject an output failure to check cleanup and destination preservation."""
        path.write_bytes(b"partial")
        raise CorruptedFileError("injected failure")

    monkeypatch.setattr(output_module, "_write_frame", fail)
    with pytest.raises(CorruptedFileError, match="injected"):
        write(_frame(), destination, overwrite=True)
    assert destination.read_bytes() == b"original"
    assert list(tmp_path.glob(".data.csv.*.tmp")) == []


def test_no_overwrite_publication_detects_destination_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that no overwrite publication detects destination race.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    destination = tmp_path / "race.csv"
    original = output_module._write_frame  # pyright: ignore[reportPrivateUsage]

    def race(dataframe: pd.DataFrame, path: Path, format: object) -> None:
        """Create a competing destination during publication to test race handling."""
        original(dataframe, path, format)  # type: ignore[arg-type]
        destination.write_bytes(b"racer")

    monkeypatch.setattr(output_module, "_write_frame", race)
    with pytest.raises(OutputExistsError, match="created during"):
        write(_frame(), destination)
    assert destination.read_bytes() == b"racer"
    assert list(tmp_path.glob(".race.csv.*.tmp")) == []


@pytest.mark.parametrize("format", ["parquet", "csv", "txt"])
def test_streaming_convert_round_trip(tmp_path: Path, format: str) -> None:
    """Verify that streaming convert round trip.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "source.csv"
    source.write_text(
        "Time/s,Current (A),Voltage (mV)\n"
        "10,0.001,3000\n11,-0.002,3100\n12,0.003,3200\n",
        encoding="utf-8",
    )
    destination = tmp_path / f"result.{format}"
    assert convert(source, destination, chunk_size=1) == destination
    pd.testing.assert_frame_equal(read(destination), _frame())
    assert list(tmp_path.glob(f".{destination.name}.*.tmp")) == []


def test_streaming_parquet_conversion_writes_multiple_row_groups(
    tmp_path: Path,
) -> None:
    """Verify that streaming parquet conversion writes multiple row groups.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "source.csv"
    source.write_text(
        "Time/s,Current/mA,Voltage/V\n0,1,3\n1,2,4\n2,3,5\n",
        encoding="utf-8",
    )
    destination = convert(source, tmp_path / "result.parquet", chunk_size=1)
    assert pq.ParquetFile(destination).num_row_groups == 3


def test_convert_explicit_format_overrides_suffix(tmp_path: Path) -> None:
    """Verify that convert explicit format overrides suffix.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "source.csv"
    source.write_text("Time/s,Current/mA,Voltage/V\n0,1,3\n1,2,4\n", encoding="utf-8")
    destination = convert(source, tmp_path / "result.data", format="txt")
    assert destination.read_text(encoding="utf-8").startswith(
        "time_s\tcurrent_mA\tvoltage_V"
    )


@pytest.mark.parametrize("existing", [False, True])
def test_late_conversion_failure_never_publishes_partial_output(
    tmp_path: Path, existing: bool
) -> None:
    """Verify that late conversion failure never publishes partial output.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "late.csv"
    source.write_text(
        "Time/s,Current/mA,Voltage/V\n0,1,3\n1,2,4\n0.5,3,5\n",
        encoding="utf-8",
    )
    destination = tmp_path / "result.parquet"
    if existing:
        destination.write_bytes(b"original")
    with pytest.raises(NonMonotonicTimeError):
        convert(source, destination, overwrite=existing, chunk_size=1)
    if existing:
        assert destination.read_bytes() == b"original"
    else:
        assert not destination.exists()
    assert list(tmp_path.glob(".result.parquet.*.tmp")) == []


def test_convert_refuses_existing_destination_without_consuming_it(
    tmp_path: Path,
) -> None:
    """Verify that convert refuses existing destination without consuming it.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "source.csv"
    source.write_text("Time/s,Current/mA,Voltage/V\n0,1,3\n1,2,4\n", encoding="utf-8")
    destination = tmp_path / "result.csv"
    destination.write_bytes(b"original")
    with pytest.raises(OutputExistsError):
        convert(source, destination)
    assert destination.read_bytes() == b"original"


def test_canonical_text_with_nonzero_origin_is_not_repaired(tmp_path: Path) -> None:
    """Verify that canonical text with nonzero origin is not repaired.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "canonical.csv"
    source.write_text("time_s,current_mA,voltage_V\n10,1,3\n11,2,4\n", encoding="utf-8")
    with pytest.raises(IncompatibleDataError, match="must be 0"):
        read(source)
    iterator = output_module.iter_read(source, chunk_size=1)
    first = next(iterator)
    assert first.loc[0, "time_s"] == 10.0
    next(iterator)
    with pytest.raises(IncompatibleDataError, match="must be 0"):
        next(iterator)
