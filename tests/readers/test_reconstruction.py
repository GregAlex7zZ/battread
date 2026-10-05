# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for reconstruction.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from battread import convert, iter_read, read
from battread.exceptions import (
    CurrentReconstructionError,
    IncompatibleDataError,
    NonMonotonicTimeError,
)
from battread.readers.models import CapacityKind
from battread.recognition.models import IntervalAlignment
from battread.warnings import MissingValueWarning


@pytest.mark.parametrize("rows", ["", ",0,3\n,1,3", "0,0,3\n1,inf,3"])
def test_invalid_canonical_source_fails(tmp_path: Path, rows: str) -> None:
    """Verify that invalid canonical source fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "invalid.csv"
    source.write_text("Time (s),Capacity (mAh),Voltage (V)\n" + rows)
    with pytest.raises(IncompatibleDataError):
        read(source, columns={"capacity": 1}, capacity_kind="cumulative_signed")


@pytest.mark.parametrize("chunk_size", [1, 2, 5])
def test_pair_streaming(tmp_path: Path, chunk_size: int) -> None:
    """Verify that pair streaming.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "pair.csv"
    source.write_text(
        "Time (s),Charge Capacity (mAh),Discharge Capacity (mAh),Voltage (V)\n"
        "0,0,0,3\n1,1,0,3\n2,1,2,3\n3,2,2,3\n"
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingValueWarning)
        full = read(source)
        streamed = pd.concat(
            list(iter_read(source, chunk_size=chunk_size)), ignore_index=True
        )
    pd.testing.assert_frame_equal(full, streamed)


def test_explicit_signed_cannot_hide_known_capacity_reset(tmp_path: Path) -> None:
    """Verify that explicit signed cannot hide known capacity reset.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "reset.csv"
    source.write_text(
        "Time (s),Charge Capacity (mAh),Voltage (V)\n0,0,3\n1,1,3\n2,0,3\n"
    )
    with pytest.raises(CurrentReconstructionError):
        read(source, columns={"capacity": 1}, capacity_kind="cumulative_signed")


@pytest.mark.parametrize("alignment", ["previous", "next"])
def test_incremental_missing_time_never_bridges(
    tmp_path: Path, alignment: IntervalAlignment
) -> None:
    """Verify that incremental missing time never bridges.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "missing.csv"
    source.write_text(
        "Time (s),Capacity (mAh),Voltage (V)\n0,1,3\n,1,3\n2,1,3\n3,1,3\n"
    )
    with pytest.warns(MissingValueWarning):
        result = read(
            source,
            columns={"capacity": 1},
            capacity_kind="delta_signed",
            capacity_interval=alignment,
        )
    expected = (
        [np.nan, np.nan, np.nan, 3600.0]
        if alignment == "previous"
        else [np.nan, np.nan, 3600.0, np.nan]
    )
    np.testing.assert_allclose(result.current_mA, expected, equal_nan=True)


@pytest.mark.parametrize("chunk_size", [1, 2, 3, 20])
@pytest.mark.parametrize(
    "kind,alignment,expected",
    [
        ("cumulative_signed", None, [np.nan, 3600.0, -7200.0, 0.0]),
        ("delta_signed", "previous", [np.nan, 3600.0, -3600.0, -3600.0]),
        ("delta_signed", "next", [0.0, 3600.0, -3600.0, np.nan]),
    ],
)
def test_signed_chunk_equivalence(
    tmp_path: Path,
    chunk_size: int,
    kind: CapacityKind,
    alignment: IntervalAlignment | None,
    expected: list[float],
) -> None:
    """Verify that signed chunk equivalence.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "source.csv"
    source.write_text(
        "Time (s),Capacity (mAh),Voltage (V)\n10,0,3\n11,1,3\n12,-1,3\n13,-1,3\n"
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingValueWarning)
        complete = read(
            source,
            columns={"capacity": "Capacity (mAh)"},
            capacity_kind=kind,
            capacity_interval=alignment,
        )  # pyright: ignore[reportArgumentType]
        chunks = list(
            iter_read(
                source,
                chunk_size=chunk_size,
                columns={"capacity": "Capacity (mAh)"},
                capacity_kind=kind,
                capacity_interval=alignment,
            )
        )  # pyright: ignore[reportArgumentType]
    np.testing.assert_allclose(complete.current_mA, expected, equal_nan=True)
    pd.testing.assert_frame_equal(complete, pd.concat(chunks, ignore_index=True))


def test_pair_units_and_sign(tmp_path: Path) -> None:
    """Verify that pair units and sign.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "pair.csv"
    source.write_text(
        "Time (h),Charge Capacity (Ah),Discharge Capacity (mAh),Voltage (V)\n"
        "0,0,0,3\n1,0.001,0,3\n2,0.001,2,3\n"
    )
    with pytest.warns(MissingValueWarning):
        result = read(source)
    np.testing.assert_allclose(result.current_mA, [np.nan, 1.0, -2.0], equal_nan=True)


@pytest.mark.parametrize(
    "capacities", ["0,0\n1,0\n0,0", "0,0\n0,1\n0,0", "1,0\n,0\n0,0"]
)
def test_pair_resets_fail(tmp_path: Path, capacities: str) -> None:
    """Verify that pair resets fail.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "reset.csv"
    lines = [f"{i},{q},3" for i, q in enumerate(capacities.splitlines())]
    source.write_text(
        "Time (s),Charge Capacity (mAh),Discharge Capacity (mAh),Voltage (V)\n"
        + "\n".join(lines)
    )
    with pytest.raises(CurrentReconstructionError):
        read(source)


@pytest.mark.parametrize(
    "time,capacity,expected",
    [
        ("0,1,1,2", "0,1,2,3", [np.nan, 3600.0, np.nan, 3600.0]),
        ("0,,2,3", "0,1,2,3", [np.nan, np.nan, np.nan, 3600.0]),
        ("0,1,2,3", "0,,2,3", [np.nan, np.nan, np.nan, 3600.0]),
    ],
)
def test_adjacent_missing_intervals(
    tmp_path: Path, time: str, capacity: str, expected: list[float]
) -> None:
    """Verify that adjacent missing intervals.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "missing.csv"
    rows = [
        f"{t},{q},3" for t, q in zip(time.split(","), capacity.split(","), strict=True)
    ]
    source.write_text("Time (s),Capacity (mAh),Voltage (V)\n" + "\n".join(rows))
    with pytest.warns(MissingValueWarning):
        result = read(
            source, columns={"capacity": 1}, capacity_kind="cumulative_signed"
        )
    np.testing.assert_allclose(result.current_mA, expected, equal_nan=True)


@pytest.mark.parametrize(
    "kind,alignment", [("delta_signed", None), ("cumulative_signed", "next")]
)
def test_alignment_errors(
    tmp_path: Path, kind: CapacityKind, alignment: IntervalAlignment | None
) -> None:
    """Verify that alignment errors.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "bad.csv"
    source.write_text("Time (s),Capacity (mAh),Voltage (V)\n0,0,3\n1,1,3\n")
    with pytest.raises(CurrentReconstructionError):
        read(
            source,
            columns={"capacity": 1},
            capacity_kind=kind,
            capacity_interval=alignment,
        )  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("rows", ["0,0,3", "0,0,3\n0,1,3", "0,,3\n1,,3"])
def test_no_finite_current_fails(tmp_path: Path, rows: str) -> None:
    """Verify that no finite current fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "empty-current.csv"
    source.write_text("Time (s),Capacity (mAh),Voltage (V)\n" + rows)
    with pytest.raises(CurrentReconstructionError):
        read(source, columns={"capacity": 1}, capacity_kind="cumulative_signed")


def test_decimal_comma_regression(tmp_path: Path) -> None:
    """Verify that decimal comma regression.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "comma.txt"
    source.write_text("Time (s);Capacity (mAh);Voltage (V)\n0,0;0,0;3,0\n1,0;0,5;3,0\n")
    with pytest.warns(MissingValueWarning):
        result = read(
            source,
            sep=";",
            decimal=",",
            columns={"capacity": 1},
            capacity_kind="cumulative_signed",
        )
    assert result.current_mA.iloc[1] == 1800.0


def test_late_reset_does_not_publish(tmp_path: Path) -> None:
    """Verify that late reset does not publish.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "reset.csv"
    destination = tmp_path / "out.parquet"
    source.write_text(
        "Time (s),Charge Capacity (mAh),Discharge Capacity (mAh),Voltage (V)\n"
        "0,0,0,3\n1,1,0,3\n2,0,0,3\n"
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingValueWarning)
        with pytest.raises(CurrentReconstructionError):
            convert(source, destination, chunk_size=1)
    assert not destination.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_backward_time_fails(tmp_path: Path) -> None:
    """Verify that backward time fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "backward.csv"
    source.write_text("Time (s),Capacity (mAh),Voltage (V)\n0,0,3\n2,1,3\n1,2,3\n")
    with pytest.raises(NonMonotonicTimeError):
        read(source, columns={"capacity": 1}, capacity_kind="cumulative_signed")
