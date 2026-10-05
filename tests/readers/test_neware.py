# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for neware.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

# pyright: reportPrivateUsage=false
import importlib.util
import math
import struct
import warnings
import zipfile
from datetime import datetime
from pathlib import Path
from typing import cast

import pandas as pd
import pytest

import battread.readers.neware as adapter
from battread import detect_format, inspect, iter_read, read
from battread.exceptions import (
    CorruptedFileError,
    MissingDependencyError,
    UnsupportedFormatError,
)
from battread.readers.models import ReadOptions
from battread.warnings import MissingValueWarning

_DATA = Path(__file__).parents[1] / "data" / "neware"
pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("NewareNDA") is None,
    reason="Install battread[neware] for vendor fixture tests",
)


def test_nda_reference() -> None:
    """Verify that nda reference.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _DATA / "prefix.nda"
    result = read(path)
    raw = path.read_bytes()[85471:]
    records = [raw[i : i + 86] for i in range(0, len(raw), 86)]
    scientific = [r for r in records if r[:2] == b"\x55\x00"]
    assert len(result) == len(scientific)
    # Independent wire-field reference, without invoking a backend decoder.
    assert result.voltage_V.tolist() == [
        struct.unpack_from("<i", r, 22)[0] / 10000 for r in scientific
    ]
    assert result.current_mA.iloc[2] == pytest.approx(-0.0294)
    assert result.current_mA.tolist() == pytest.approx(
        [struct.unpack_from("<i", r, 26)[0] * 0.0001 for r in scientific],
        rel=1e-12,
        abs=1e-14,
    )
    calendar = [datetime(*struct.unpack_from("<HBBBBB", r, 70)) for r in scientific]
    assert result.time_s.tolist() == [
        (t - calendar[0]).total_seconds() for t in calendar
    ]
    assert result.time_s.iloc[0] == 0
    assert result.time_s.iloc[1] == 0  # Recorded seconds; no fabricated precision.
    assert inspect(path).reader == "neware"


@pytest.mark.parametrize("filename", ["prefix.nda", "small.ndax"])
@pytest.mark.parametrize("size", [1, 7, 1000])
def test_chunks(filename: str, size: int) -> None:
    """Verify that chunks.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _DATA / filename
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingValueWarning)
        expected = read(path)
        actual = pd.concat(iter_read(path, chunk_size=size), ignore_index=True)
    pd.testing.assert_frame_equal(actual, expected)


def test_sparse_ndax() -> None:
    """Verify that sparse ndax.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.warns(MissingValueWarning):
        result = read(_DATA / "small.ndax")
    assert result.time_s.isna().sum() == 9
    assert result.voltage_V.iloc[0] == pytest.approx(1.11745625)
    assert all(result.current_mA == 0)
    with zipfile.ZipFile(_DATA / "small.ndax") as archive:
        primary = archive.read("data.ndc")[4096:]
        values = [
            pair
            for offset in range(0, len(primary), 4096)
            for pair in struct.iter_unpack("<ff", primary[offset + 132 : offset + 4092])
        ]
        assert result.voltage_V.tolist() == pytest.approx(
            [v * 1e-4 for v, _ in values[: len(result)]], rel=1e-12, abs=1e-14
        )
        metadata = archive.read("data_runInfo.ndc")[4096:]
        checkpoints: dict[int, float] = {}
        for offset in range(0, len(metadata), 4096):
            for r in struct.iter_unpack(
                "<ixffff8xiiiih53x", metadata[offset + 132 : offset + 4032]
            ):
                if r[8]:
                    checkpoints[int(r[8])] = int(r[6]) + int(r[9]) / 1000
        origin = checkpoints[1]
        for index, time in enumerate(result.time_s, start=1):
            if index in checkpoints:
                assert time == pytest.approx(checkpoints[index] - origin, abs=1e-6)
            else:
                assert math.isnan(cast(float, time))


@pytest.mark.parametrize("bts91", [False, True])
def test_nda130_wire_reference(tmp_path: Path, bts91: bool) -> None:
    """Verify that nda130 wire reference.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    header = bytearray(1024)
    header[:6] = b"NEWARE"
    header[14] = 130
    records: list[bytes] = []
    for index, current in enumerate([2.5, -1.25, 0.0], start=1):
        if bts91:
            record = bytearray(56)
            record[:4] = b"\x55\x00\x01\x04"
            struct.pack_into("<III", record, 8, index, 0, 0)
            struct.pack_into("<ff", record, 20, current, 3.5)
            struct.pack_into("<II", record, 44, 1_700_000_000 + index * 2, 125_000_000)
        else:
            record = bytearray(88)
            record[:6] = b"\x12\x00\x00\x00\x55\x00"
            record[9:11] = b"\x01\x04"
            struct.pack_into("<I", record, 16, index)
            struct.pack_into("<Qff", record, 28, 0, 3.5, current)
            struct.pack_into(
                "<Q", record, 68, (1_700_000_000 + index * 2) * 1_000_000 + 125_000
            )
        records.append(bytes(record))
    path = tmp_path / "reference.nda"
    path.write_bytes(header + b"".join(records))
    expected = pd.DataFrame(
        {
            "time_s": [0.0, 2.0, 4.0],
            "current_mA": [2.5, -1.25, 0.0],
            "voltage_V": [3.5] * 3,
        }
    )
    pd.testing.assert_frame_equal(read(path), expected)
    pd.testing.assert_frame_equal(
        pd.concat(iter_read(path, chunk_size=1), ignore_index=True), expected
    )


@pytest.mark.parametrize("version", [2, 5])
def test_full_ndax_wire_reference(tmp_path: Path, version: int) -> None:
    """Verify that full ndax wire reference.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    header = bytearray(517 if version == 2 else 4096)
    header[0] = 1
    header[2] = version
    records: list[bytes] = []
    for index, current in enumerate([25000, -12500, 0], start=1):
        record = bytearray(94 if version == 2 else 87)
        record[0 if version == 2 else 7] = 0x55
        struct.pack_into("<IIBB", record, 8, index, 0, 1, 4)
        struct.pack_into("<Qii", record, 23, 0, 35000, current)
        struct.pack_into("<HBBBBB", record, 75, 2024, 1, 1, 12, 0, index * 2)
        struct.pack_into("<i", record, 82, 5)
        records.append(bytes(record))
    if version == 5:
        block = bytearray(4096)
        block[125 : 125 + len(b"".join(records))] = b"".join(records)
        payload = header + block
    else:
        payload = header + b"".join(records)
    path = tmp_path / "reference.ndax"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("data.ndc", payload)
    expected = pd.DataFrame(
        {
            "time_s": [0.0, 2.0, 4.0],
            "current_mA": [2.5, -1.25, 0.0],
            "voltage_V": [3.5] * 3,
        }
    )
    pd.testing.assert_frame_equal(read(path), expected)
    pd.testing.assert_frame_equal(
        pd.concat(iter_read(path, chunk_size=1), ignore_index=True), expected
    )


@pytest.mark.parametrize("version", [11, 14, 16, 17])
def test_split_ndax_wire_reference(tmp_path: Path, version: int) -> None:
    """Verify that split ndax wire reference.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    primary_header = bytearray(4096)
    primary_header[0], primary_header[2] = 1, version
    run_header = bytearray(primary_header)
    run_header[0] = 18
    primary, metadata = bytearray(4096), bytearray(4096)
    layout = {
        11: "<ixffff8xiiiih",
        14: "<ixffff8xiiiih8x",
        16: "<ixffff8xiiiih53x",
        17: "<ixffff8xiiiih53x",
    }[version]
    size = struct.calcsize(layout)
    for index, (current, voltage) in enumerate(
        [(2.5, 3.5), (-1.25, 0), (0, 3.5)], start=1
    ):
        struct.pack_into(
            "<ff",
            primary,
            132 + (index - 1) * 8,
            voltage * (10000 if version in {11, 16} else 1),
            current / (1000 if version in {14, 17} else 1),
        )
        struct.pack_into(
            layout,
            metadata,
            132 + (index - 1) * size,
            0,
            0,
            0,
            0,
            0,
            0,
            1_700_000_000 + index * 2,
            1,
            index,
            125,
        )
    path = tmp_path / "reference.ndax"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("data.ndc", primary_header + primary)
        archive.writestr("data_runInfo.ndc", run_header + metadata)
    expected = pd.DataFrame(
        {
            "time_s": [0.0, 2.0, 4.0],
            "current_mA": [2.5, -1.25, 0.0],
            "voltage_V": [3.5, 0, 3.5],
        }
    )
    pd.testing.assert_frame_equal(read(path), expected, rtol=1e-7)
    pd.testing.assert_frame_equal(
        pd.concat(iter_read(path, chunk_size=1), ignore_index=True), expected, rtol=1e-7
    )


def test_conflicting_checkpoints() -> None:
    """Verify that conflicting checkpoints.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(CorruptedFileError, match="Conflicting"):
        read(_DATA / "conflicting.ndax")


def test_truncated_nda(tmp_path: Path) -> None:
    """Verify that truncated nda.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "broken.nda"
    path.write_bytes((_DATA / "prefix.nda").read_bytes()[:-1])
    with pytest.raises(CorruptedFileError, match="Truncated"):
        read(path)


def test_unknown_record_not_skipped(tmp_path: Path) -> None:
    """Verify that unknown record not skipped.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "unknown.nda"
    content = bytearray((_DATA / "prefix.nda").read_bytes())
    content[85471 + 86] = 0xAA
    path.write_bytes(content)
    with pytest.raises(CorruptedFileError, match="framing"):
        read(path)


def test_duplicate_measurements_retained(tmp_path: Path) -> None:
    """Verify that duplicate measurements retained.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "duplicate.nda"
    raw = (_DATA / "prefix.nda").read_bytes()
    path.write_bytes(raw[:85471] + raw[85471:85557] * 2)
    result = read(path)
    assert len(result) == 2
    assert result.time_s.tolist() == [0, 0]


def test_detection_uses_content(tmp_path: Path) -> None:
    """Verify that detection uses content.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "wrong.bin"
    path.write_bytes((_DATA / "small.ndax").read_bytes())
    assert detect_format(path).format == "ndax"


def test_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that missing dependency.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """

    def unavailable(name: str) -> object:
        """Simulate a missing optional backend to verify actionable dependency
        errors."""
        raise ImportError(name)

    monkeypatch.setattr(adapter, "import_module", unavailable)
    with pytest.raises(MissingDependencyError, match="battread\\[neware\\]"):
        read(_DATA / "prefix.nda")


def test_explicit_reader_invalid_source(tmp_path: Path) -> None:
    """Verify that explicit reader invalid source.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "unrecognized.bin"
    path.write_bytes(b"not scientific data")
    with pytest.raises(UnsupportedFormatError, match=r"[Nn]eware"):
        read(path, reader="neware")
    with pytest.raises(UnsupportedFormatError, match=r"[Nn]eware"):
        inspect(path, reader="neware")
    with pytest.raises(UnsupportedFormatError, match="Neware"):
        adapter.NewareReader().read(path, ReadOptions())
    with pytest.raises(UnsupportedFormatError, match="Neware"):
        adapter.NewareReader().inspect(path, ReadOptions())
