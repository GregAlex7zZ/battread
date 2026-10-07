# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for clock time.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

from pathlib import Path

import pandas as pd
import pytest

from battread import inspect, iter_read, read
from battread.exceptions import (
    AmbiguousColumnError,
    IncompatibleDataError,
    NonMonotonicTimeError,
)
from battread.warnings import MalformedValueWarning, MissingValueWarning


def test_elapsed_clock(tmp_path: Path) -> None:
    """Verify that elapsed clock.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "clock.csv"
    path.write_text("Total Time,I/mA,Voltage(V)\n25:00:00,1,3\n25:00:01.125,-1,3\n")
    result = read(path, columns={"time": "Total Time"}, units={"time": "s"})
    assert result.time_s.tolist() == [0, 1.125]
    with pytest.raises(IncompatibleDataError, match="seconds"):
        read(path, columns={"time": "Total Time"}, units={"time": "h"})


def test_invalid_clock_retained(tmp_path: Path) -> None:
    """Verify that invalid clock retained.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "clock.csv"
    path.write_text("time_s,current_mA,voltage_V\n0,1,3\n00:60:00,1,3\n")
    with pytest.warns((MalformedValueWarning, MissingValueWarning)):
        result = read(path)
    assert len(result) == 2
    assert result.time_s.isna().iloc[1]


def test_neware_csv_total_time(tmp_path: Path) -> None:
    """Verify that neware csv total time.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "neware.csv"
    path.write_text(
        "DataPoint,Step Type,Time,Total Time,Current(mA),Voltage(V),"
        "Capacity(mAh),Energy(Wh),Date,Power(W)\n"
        "1,Rest,00:00:00,25:00:00,0,3,0,0,2025-03-27,0\n"
        "2,Charge,00:00:01,25:00:02.5,-1,3,0,0,2025-03-27,0\n"
        "3,Rest,00:00:00,25:00:03,0,3,0,0,2025-03-27,0\n"
    )
    result = read(path)
    assert result.time_s.tolist() == [0, 2.5, 3]
    assert result.current_mA.tolist() == [0, -1, 0]
    actual = pd.concat(iter_read(path, chunk_size=1), ignore_index=True)
    pd.testing.assert_frame_equal(actual, result)
    match = next(m for m in inspect(path).columns if m.source_column == "Total Time")
    assert match.state == "resolved"
    assert "Neware CSV" in match.evidence[0]
    with pytest.raises(NonMonotonicTimeError):
        read(path, columns={"time": "Time"}, units={"time": "s"})


@pytest.mark.parametrize("step_header", [None, "Unnamed: 1"])
def test_neware_csv_optional_step_label(
    tmp_path: Path, step_header: str | None
) -> None:
    """Recognize optional step labels and ignore resets across chunk boundaries."""
    path = tmp_path / "optional-step.csv"
    headers = ["Unnamed: 0"]
    if step_header is not None:
        headers.append(step_header)
    headers.extend(
        [
            "DataPoint",
            "Time",
            "Total Time",
            "Current(mA)",
            "Voltage(V)",
            "Capacity(mAh)",
            "Energy(Wh)",
            "Date",
            "Power(W)",
            "Unnamed: 11",
        ]
    )
    rows: list[str] = []
    for number, step, total, current in [
        (1, "00:00:00", "25:00:00", 0),
        (2, "00:00:01", "25:00:02.5", -1),
        (3, "00:00:00", "25:00:03", 2),
    ]:
        values = [""] + (["Rest"] if step_header is not None else [])
        values.extend(
            [
                str(number),
                step,
                total,
                str(current),
                "3.5",
                "0",
                "0",
                "2025-01-01",
                "0",
                "",
            ]
        )
        rows.append(",".join(values))
    path.write_text(",".join(headers) + "\n" + "\n".join(rows) + "\n")
    result = read(path)
    assert result.time_s.tolist() == [0, 2.5, 3]
    assert result.current_mA.tolist() == [0, -1, 2]
    for chunk_size in (1, 2, 10):
        actual = pd.concat(iter_read(path, chunk_size=chunk_size), ignore_index=True)
        pd.testing.assert_frame_equal(actual, result)
    matches = inspect(path).columns
    selected = next(m for m in matches if m.source_column == "Total Time")
    rejected = next(m for m in matches if m.source_column == "Time")
    assert selected.state == "resolved" and selected.unit == "s"
    assert "Neware CSV" in selected.evidence[0]
    assert rejected.state == "unresolved"
    assert any("step or calendar time rejected" in item for item in rejected.evidence)


def test_generic_paired_times_select_total_time(tmp_path: Path) -> None:
    """The documented paired-clock policy does not depend on vendor recognition."""
    path = tmp_path / "generic.csv"
    path.write_text("Time(s),Total Time(s),Current(mA),Voltage(V)\n0,0,1,3\n")
    result = read(path)
    assert result.time_s.tolist() == [0]
    selected = next(
        m for m in inspect(path).columns if m.source_column == "Total Time(s)"
    )
    assert "CSV time preference" in selected.evidence[-1]


def test_neware_duplicate_total_clocks_remain_ambiguous(tmp_path: Path) -> None:
    """A verified vendor profile cannot choose between two total elapsed columns."""
    path = tmp_path / "duplicate-clock.csv"
    path.write_text(
        "DataPoint,Time,Total Time,Total Time,Current(mA),Voltage(V),"
        "Capacity(mAh),Energy(Wh),Date,Power(W)\n"
        "1,00:00:00,00:00:00,00:00:01,1,3,0,0,2025-01-01,0\n"
    )
    with pytest.raises(AmbiguousColumnError):
        read(path)


@pytest.mark.parametrize(
    "header,rows,expected",
    [
        ("Time,Total Time", "0,25:00:00\n0,25:00:01.25", [0, 1.25]),
        ("Time(s),Total Time(h)", "0,2\n1,3", [0, 3600]),
        (" TIME [s],total_time (ms)", "0,2000\n1,3250", [0, 1.25]),
    ],
)
def test_csv_total_clock_policy_units_and_chunks(
    tmp_path: Path, header: str, rows: str, expected: list[float]
) -> None:
    """Prefer normalized paired clocks, preserving declared scales and chunk results."""
    path = tmp_path / "clocks.csv"
    lines = rows.splitlines()
    path.write_text(
        header
        + ",Current(mA),Voltage(V)\n"
        + "\n".join(line + ",-1,3.5" for line in lines)
        + "\n"
    )
    result = read(path)
    assert result.time_s.tolist() == expected
    actual = pd.concat(iter_read(path, chunk_size=1), ignore_index=True)
    pd.testing.assert_frame_equal(actual, result)


def test_csv_clock_policy_explicit_mapping_wins(tmp_path: Path) -> None:
    """An explicit time mapping takes precedence over the CSV default preference."""
    path = tmp_path / "explicit.csv"
    path.write_text("Time(s),Total Time(h),Current(mA),Voltage(V)\n0,2,1,3\n1,3,1,3\n")
    assert read(path, columns={"time": 0}).time_s.tolist() == [0, 1]


def test_csv_other_time_ambiguity_is_not_suppressed(tmp_path: Path) -> None:
    """Unrelated measured time columns still require an explicit scientific choice."""
    path = tmp_path / "other.csv"
    path.write_text("Time(s),Time(s),Current(mA),Voltage(V)\n0,0,1,3\n")
    with pytest.raises(AmbiguousColumnError):
        read(path)


def test_csv_unknown_total_unit_does_not_default_to_seconds(tmp_path: Path) -> None:
    """A unit suffix outside the registry must fail rather than become seconds."""
    from battread.exceptions import UnknownUnitError

    path = tmp_path / "unknown.csv"
    path.write_text("Time(s),Total Time(furlong),Current(mA),Voltage(V)\n0,1,1,3\n")
    with pytest.raises(UnknownUnitError):
        read(path)
