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
from battread.exceptions import IncompatibleDataError, NonMonotonicTimeError
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
