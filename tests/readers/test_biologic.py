# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for biologic.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

# Shared adapter internals are exercised to test optional backend failure paths.
# pyright: reportPrivateUsage=false

import csv
import importlib.util
import struct
import warnings
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import battread.readers.biologic as adapter
from battread import convert, detect_format, inspect, iter_read, read
from battread._pandas import numpy_values
from battread.exceptions import (
    AmbiguousColumnError,
    CorruptedFileError,
    CurrentReconstructionError,
    IncompatibleDataError,
    MissingColumnError,
    MissingDependencyError,
    NonMonotonicTimeError,
    UnsupportedFormatError,
)
from battread.readers.models import CapacityKind, ReadOptions
from battread.recognition.models import IntervalAlignment
from battread.warnings import MalformedValueWarning, MissingValueWarning

_DATA = Path(__file__).parents[1] / "data" / "biologic"
_HAS_GALVANI = importlib.util.find_spec("galvani") is not None
_BINARY = pytest.mark.skipif(
    not _HAS_GALVANI, reason="Install battread[biologic] for real MPR tests"
)


def _mpt(path: Path, header: str, rows: str, *, decimal_comma: bool = False) -> Path:
    """Write a synthetic MPT header and records without relying on vendor software."""
    content = "EC-Lab ASCII FILE\nNb header lines : 3\n" + header + "\n" + rows
    if decimal_comma:
        content = content.replace(".", ",")
    path.write_text(content, encoding="utf-8")
    return path


def _mpr(
    path: Path, ids: list[int], rows: list[tuple[float, ...]], layout: str
) -> Path:
    """Construct bytes independently of Galvani; no backend generates expected data."""

    def module(name: bytes, version: int, payload: bytes) -> bytes:
        """Supply a synthetic backend module to exercise adapter isolation."""
        return (
            b"MODULE"
            + struct.pack("<10s25sII8s", name, name, len(payload), version, b"01/01/24")
            + payload
        )

    header = struct.pack("<IB", len(rows), len(ids)) + struct.pack(
        "<" + "H" * len(ids), *ids
    )
    payload = header.ljust(405, b"\x00") + b"".join(
        struct.pack(layout, *row) for row in rows
    )
    path.write_bytes(
        adapter._MPR_MAGIC
        + module(b"VMP Set   ", 0, b"")
        + module(b"VMP data  ", 2, payload)
    )
    return path


def _reference() -> pd.DataFrame:
    """Read the independent BT-Lab ASCII export with the stdlib CSV parser."""
    with (_DATA / "020-formation_CB5.mpt").open(
        encoding="cp1252", newline=""
    ) as stream:
        assert stream.readline().strip() == "BT-Lab ASCII FILE"
        count = int(stream.readline().split(":")[1])
        for _ in range(count - 3):
            stream.readline()
        header = stream.readline().strip().split("\t")
        positions = [header.index(name) for name in ("time/s", "I/mA", "Ecell/V")]
        rows = [
            [float(row[i]) for i in positions]
            for row in csv.reader(stream, delimiter="\t")
            if row
        ]
    result = pd.DataFrame(
        rows, columns=["time_s", "current_mA", "voltage_V"], dtype="float64"
    )
    result["time_s"] = result["time_s"] - result["time_s"].iloc[0]
    return result


@pytest.mark.parametrize("extension", ["mpr", "mpt"])
def test_magic_detection(extension: str) -> None:
    """Verify that magic detection.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    info = detect_format(_DATA / f"020-formation_CB5.{extension}")
    assert info.format == extension
    assert info.reader == f"biologic-{extension}"
    assert info.confidence == 1.0


def test_real_mpt_matches_independent_reference() -> None:
    """Verify that real mpt matches independent reference.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = read(_DATA / "020-formation_CB5.mpt")
    pd.testing.assert_frame_equal(result, _reference())
    assert any(result.current_mA < 0)
    assert any(result.current_mA > 0)


@pytest.mark.parametrize("include_reset", [False, True])
def test_real_export_capacity_reference(tmp_path: Path, include_reset: bool) -> None:
    # Exclude the direct-current field from an independently exported table.
    # Row 588 (zero-based) is the first charge-capacity reset in this acquisition.
    """Verify that real export capacity reference.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with (_DATA / "020-formation_CB5.mpt").open(encoding="cp1252") as stream:
        lines = stream.readlines()
    names = lines[92].strip().split("\t")
    positions = [
        names.index(name)
        for name in ("time/s", "Ecell/V", "Q charge/mA.h", "Q discharge/mA.h")
    ]
    records = [row for row in csv.reader(lines[93:], delimiter="\t") if row]
    records = records[: 589 if include_reset else 588]
    selected = [[row[i] for i in positions] for row in records]
    path = _mpt(
        tmp_path / "export-capacity.mpt",
        "time/s\tEcell/V\tQ charge/mA.h\tQ discharge/mA.h",
        "\n".join("\t".join(row) for row in selected),
    )
    if include_reset:
        with pytest.raises(CurrentReconstructionError):
            read(path)
    else:
        values = np.asarray(selected, dtype="float64")
        expected = (
            3600
            * ((values[1:, 2] - values[:-1, 2]) - (values[1:, 3] - values[:-1, 3]))
            / (values[1:, 0] - values[:-1, 0])
        )
        with pytest.warns(MissingValueWarning):
            result = read(path)
        np.testing.assert_allclose(
            result.current_mA, np.r_[np.nan, expected], equal_nan=True
        )


def test_backend_is_not_imported_by_generic_core(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that backend is not imported by generic core.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """

    def unavailable(name: str) -> object:
        """Simulate a missing optional backend to verify actionable dependency
        errors."""
        raise AssertionError(f"Unexpected vendor import: {name}")

    monkeypatch.setattr(adapter, "import_module", unavailable)
    generic = tmp_path / "generic.csv"
    generic.write_text("time_s,current_mA,voltage_V\n0,-1,3\n")
    assert read(generic).current_mA.tolist() == [-1.0]
    mpt = _mpt(tmp_path / "native.mpt", "time/s\tI/mA\tEwe/V", "0\t-1\t3\n")
    assert read(mpt).current_mA.tolist() == [-1.0]


@_BINARY
def test_real_mpr_matches_independent_export() -> None:
    """Verify that real mpr matches independent export.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    result = read(_DATA / "020-formation_CB5.mpr")
    np.testing.assert_allclose(
        numpy_values(result), numpy_values(_reference()), rtol=1e-7, atol=1e-7
    )
    assert [str(dtype) for dtype in result.dtypes] == ["float64"] * 3


@pytest.mark.parametrize("chunk_size", [1, 17, 250_000])
@pytest.mark.parametrize("extension", ["mpt", pytest.param("mpr", marks=_BINARY)])
def test_real_chunk_equivalence(extension: str, chunk_size: int) -> None:
    """Verify that real chunk equivalence.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _DATA / f"020-formation_CB5.{extension}"
    pd.testing.assert_frame_equal(
        read(source),
        pd.concat(list(iter_read(source, chunk_size=chunk_size)), ignore_index=True),
    )


@pytest.mark.parametrize("extension", ["mpt", pytest.param("mpr", marks=_BINARY)])
def test_real_conversion(tmp_path: Path, extension: str) -> None:
    """Verify that real conversion.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _DATA / f"020-formation_CB5.{extension}"
    target = convert(source, tmp_path / "result.parquet", chunk_size=17)
    pd.testing.assert_frame_equal(read(source), read(target))


def test_mpt_inspection_and_magic_with_wrong_suffix(tmp_path: Path) -> None:
    """Verify that mpt inspection and magic with wrong suffix.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(tmp_path / "input.csv", "time/s\tI/mA\tEwe/V", "5\t-2\t3\n6\t4\t3\n")
    assert detect_format(path).format == "mpt"
    information = inspect(path)
    assert information.delimiter == "\t"
    assert information.current_reconstruction_required is False
    assert all(
        "authoritative" in " ".join(match.evidence) for match in information.columns
    )
    assert read(path, reader="mpt").time_s.tolist() == [0.0, 1.0]


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_decimal_comma_and_padding(tmp_path: Path, newline: str) -> None:
    """Verify that decimal comma and padding.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "decimal.mpt"
    path.write_bytes(
        (
            "EC-Lab ASCII FILE\nNb header lines : 3\ntime/s\t<I>/mA\t<Ewe>/V\t\n"
            "0,0\t-2,5\t3,0\t\n1,0\t2,5\t3,1\n"
        )
        .replace("\n", newline)
        .encode()
    )
    result = read(path)
    assert result.current_mA.tolist() == [-2.5, 2.5]
    assert result.voltage_V.tolist() == [3.0, 3.1]


@pytest.mark.parametrize(
    "body",
    [
        "bad\n",
        "EC-Lab ASCII FILE\nwrong\n",
        "EC-Lab ASCII FILE\nNb header lines : 2\n",
        "EC-Lab ASCII FILE\nNb header lines : 5\ntime/s\tI/mA\tEwe/V\n",
    ],
)
def test_invalid_mpt_header(tmp_path: Path, body: str) -> None:
    """Verify that invalid mpt header.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "bad.mpt"
    path.write_text(body)
    with pytest.raises(CorruptedFileError):
        read(path)


@pytest.mark.parametrize("row", ["1\t2\n", "1\t2\t3\t4\n"])
def test_malformed_mpt_record_fails(tmp_path: Path, row: str) -> None:
    """Verify that malformed mpt record fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(tmp_path / "bad.mpt", "time/s\tI/mA\tEwe/V", "0\t1\t3\n" + row)
    with pytest.raises(CorruptedFileError):
        read(path)


def test_mpt_missing_and_malformed_current_retained(tmp_path: Path) -> None:
    """Verify that mpt missing and malformed current retained.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(
        tmp_path / "missing.mpt",
        "time/s\tI/mA\tEwe/V\tQ charge/mA.h\tQ discharge/mA.h",
        "0\t\t3\t0\t0\n1\tbad\t3\t1\t0\n",
    )
    with pytest.warns((MissingValueWarning, MalformedValueWarning)):
        result = read(path)
    assert all(result.current_mA.isna())
    assert len(result) == 2


@pytest.mark.parametrize("name", ["Ecell/V", "Ewe/V", "<Ewe>/V", "<Ewe/V>"])
def test_voltage_aliases(tmp_path: Path, name: str) -> None:
    """Verify that voltage aliases.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(tmp_path / "alias.mpt", f"time/s\tI/mA\t{name}", "0\t-1\t3\n")
    assert read(path).voltage_V.tolist() == [3.0]


def test_ac_magnitude_does_not_supply_signed_current(tmp_path: Path) -> None:
    """Verify that ac magnitude does not supply signed current.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(tmp_path / "magnitude.mpt", "time/s\t|I|/A\tEwe/V", "0\t1\t3\n")
    match = inspect(path).columns[1]
    assert match.state == "unresolved"
    assert "AC magnitude" in " ".join(match.evidence)
    with pytest.raises(MissingColumnError):
        read(path)


def test_ambiguous_voltage_requires_mapping(tmp_path: Path) -> None:
    """Verify that ambiguous voltage requires mapping.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(
        tmp_path / "ambiguous.mpt", "time/s\tI/mA\tEwe/V\tEcell/V", "0\t1\t3\t4\n"
    )
    assert any(match.state == "ambiguous" for match in inspect(path).columns)
    with pytest.raises(AmbiguousColumnError):
        read(path)
    assert read(path, columns={"voltage": "Ecell/V"}).voltage_V.tolist() == [4.0]


@pytest.mark.parametrize(
    "kind,alignment",
    [
        ("cumulative_signed", None),
        ("delta_signed", "previous"),
        ("delta_signed", "next"),
    ],
)
def test_explicit_capacity_paths(
    tmp_path: Path, kind: CapacityKind, alignment: IntervalAlignment | None
) -> None:
    """Verify that explicit capacity paths.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(
        tmp_path / "capacity.mpt",
        "time/s\tEwe/V\tdq/mA.h",
        "0\t3\t0\n1\t3\t1\n2\t3\t-1\n",
    )
    assert inspect(path).current_reconstruction_required is True
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingValueWarning)
        complete = read(
            path,
            columns={"capacity": "dq/mA.h"},
            capacity_kind=kind,
            capacity_interval=alignment,
        )
        streamed = pd.concat(
            list(
                iter_read(
                    path,
                    chunk_size=1,
                    columns={"capacity": "dq/mA.h"},
                    capacity_kind=kind,
                    capacity_interval=alignment,
                )
            ),
            ignore_index=True,
        )
    pd.testing.assert_frame_equal(complete, streamed)


@pytest.mark.parametrize("extension", ["mpt", pytest.param("mpr", marks=_BINARY)])
@pytest.mark.parametrize("chunk_size", [1, 17, 250_000])
def test_real_signed_dq_reference(
    tmp_path: Path, extension: str, chunk_size: int
) -> None:
    """Verify that real signed dq reference.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with (_DATA / "020-formation_CB5.mpt").open(encoding="cp1252") as stream:
        lines = stream.readlines()
    names = lines[92].strip().split("\t")
    selected_names = [
        "time/s",
        "Ecell/V",
        "dq/mA.h",
        "Q charge/mA.h",
        "Q discharge/mA.h",
    ]
    positions = [names.index(name) for name in selected_names]
    values = [
        [float(row[i]) for i in positions]
        for row in csv.reader(lines[93:], delimiter="\t")
        if row
    ]
    if extension == "mpt":
        path = _mpt(
            tmp_path / "real-dq.mpt",
            "\t".join(selected_names),
            "\n".join("\t".join(repr(v) for v in row) for row in values),
        )
    else:
        path = _mpr(
            tmp_path / "real-dq.mpr",
            [4, 6, 7],
            [tuple(row[:3]) for row in values],
            "<dfd",
        )
    expected = [np.nan]
    for left, right in pairwise(values):
        dt = right[0] - left[0]
        expected.append(3600 * right[2] / dt if dt > 0 else np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingValueWarning)
        result = read(path)
        chunks = pd.concat(
            list(iter_read(path, chunk_size=chunk_size)), ignore_index=True
        )
    np.testing.assert_allclose(result.current_mA, expected, equal_nan=True)
    pd.testing.assert_frame_equal(result, chunks)
    assert any(result.current_mA < 0)
    assert any(result.current_mA > 0)
    # Cumulative pair resets exist in this export, but the selected dq does not reset.
    assert len(result) == 1323


@pytest.mark.parametrize(
    "label,scale", [("dq/mA.h", 1.0), ("dQ/mA.h", 1.0), ("dQ/C", 3.6)]
)
def test_dq_default_and_explicit_selector(
    tmp_path: Path, label: str, scale: float
) -> None:
    """Verify that dq default and explicit selector.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(
        tmp_path / "dq.mpt",
        f"time/s\tEwe/V\t{label}",
        f"0\t3\t0\n1\t3\t{scale}\n2\t3\t{-scale}\n",
    )
    match = inspect(path).columns[2]
    assert match.semantic == "delta_signed"
    assert match.interval_alignment == "previous"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingValueWarning)
        automatic = read(path)
        selected = read(path, columns={"capacity": label})
        declared = read(path, columns={"capacity": label}, capacity_kind="delta_signed")
        overridden = read(path, capacity_interval="next")
    np.testing.assert_allclose(
        automatic.current_mA, [np.nan, 3600.0, -3600.0], equal_nan=True
    )
    pd.testing.assert_frame_equal(automatic, selected)
    pd.testing.assert_frame_equal(automatic, declared)
    np.testing.assert_allclose(
        overridden.current_mA, [0.0, 3600.0, np.nan], equal_nan=True
    )


def test_missing_measured_current_is_not_replaced_by_dq(tmp_path: Path) -> None:
    """Verify that missing measured current is not replaced by dq.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(
        tmp_path / "direct.mpt",
        "time/s\tI/mA\tEwe/V\tdq/mA.h",
        "0\t\t3\t0\n1\t\t3\t1\n",
    )
    assert inspect(path).current_reconstruction_required is False
    with pytest.warns(MissingValueWarning):
        result = read(path)
    assert all(result.current_mA.isna())


def test_multiple_dq_candidates_remain_ambiguous(tmp_path: Path) -> None:
    """Verify that multiple dq candidates remain ambiguous.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(
        tmp_path / "ambiguous-dq.mpt",
        "time/s\tEwe/V\tdq/mA.h\tdQ/mA.h",
        "0\t3\t0\t0\n1\t3\t1\t2\n",
    )
    with pytest.raises(AmbiguousColumnError):
        read(path)
    with pytest.warns(MissingValueWarning):
        result = read(path, columns={"capacity": 2})
    assert result.current_mA.iloc[1] == 3600.0


@pytest.mark.parametrize("chunk_size", [1, 2, 10])
@pytest.mark.parametrize("extension", ["mpt", pytest.param("mpr", marks=_BINARY)])
def test_automatic_pair_reconstruction(
    tmp_path: Path, chunk_size: int, extension: str
) -> None:
    """Verify that automatic pair reconstruction.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    if extension == "mpt":
        path = _mpt(
            tmp_path / "pair.mpt",
            "time/s\tEwe/V\tQ charge/mA.h\tQ discharge/mA.h",
            "0\t3\t0\t0\n1\t3\t1\t0\n2\t3\t1\t2\n",
        )
    else:
        path = _mpr(
            tmp_path / "pair.mpr",
            [4, 6, 498, 499],
            [(0.0, 3.0, 0.0, 0.0), (1.0, 3.0, 1.0, 0.0), (2.0, 3.0, 1.0, 2.0)],
            "<dfdd",
        )
    assert inspect(path).current_reconstruction_required is True
    with pytest.warns(MissingValueWarning):
        result = pd.concat(
            list(iter_read(path, chunk_size=chunk_size)), ignore_index=True
        )
    np.testing.assert_allclose(
        result.current_mA, [np.nan, 3600.0, -7200.0], equal_nan=True
    )


def test_pair_reset_preserves_existing_destination(tmp_path: Path) -> None:
    """Verify that pair reset preserves existing destination.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(
        tmp_path / "reset.mpt",
        "time/s\tEwe/V\tQ charge/mA.h\tQ discharge/mA.h",
        "0\t3\t0\t0\n1\t3\t1\t0\n2\t3\t0\t0\n",
    )
    target = tmp_path / "existing.parquet"
    target.write_bytes(b"original")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MissingValueWarning)
        with pytest.raises(CurrentReconstructionError):
            convert(path, target, overwrite=True, chunk_size=1)
    assert target.read_bytes() == b"original"


def test_missing_backend_is_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that missing backend is actionable.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "missing.mpr"
    path.write_bytes(adapter._MPR_MAGIC)

    def unavailable(name: str) -> object:
        """Simulate a missing optional backend to verify actionable dependency
        errors."""
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(adapter, "import_module", unavailable)
    assert detect_format(path).format == "mpr"
    with pytest.raises(MissingDependencyError, match=r"battread\[biologic\]"):
        read(path)


@_BINARY
@pytest.mark.parametrize("contents", [b"bad", adapter._MPR_MAGIC + b"MODULE"])
def test_corrupt_mpr(tmp_path: Path, contents: bytes) -> None:
    """Verify that corrupt mpr.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = tmp_path / "bad.mpr"
    path.write_bytes(contents)
    with pytest.raises(CorruptedFileError):
        read(path)


@_BINARY
def test_unknown_mpr_field(tmp_path: Path) -> None:
    """Verify that unknown mpr field.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpr(tmp_path / "unknown.mpr", [4, 9999], [(0.0, 3.0)], "<df")
    with pytest.raises(UnsupportedFormatError, match="schema"):
        read(path)


@_BINARY
def test_duplicate_binary_current_is_ambiguous(tmp_path: Path) -> None:
    """Verify that duplicate binary current is ambiguous.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpr(
        tmp_path / "duplicate.mpr", [4, 8, 8, 6], [(0.0, 1.0, 2.0, 3.0)], "<dfff"
    )
    with pytest.raises(AmbiguousColumnError):
        read(path)
    assert read(path, columns={"current": "I/mA 2"}).current_mA.tolist() == [2.0]


@pytest.mark.parametrize(
    "reader,options",
    [
        (adapter.BioLogicMPRReader(), ReadOptions(sep=";")),
        (adapter.BioLogicMPTReader(), ReadOptions(skiprows=1)),
    ],
)
def test_incompatible_parser_options(
    reader: adapter.DelimitedReader, options: ReadOptions
) -> None:
    """Verify that incompatible parser options.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    extension = reader.capabilities.formats[0]
    with pytest.raises(IncompatibleDataError):
        reader.inspect(_DATA / f"020-formation_CB5.{extension}", options)


def test_mpt_backward_time(tmp_path: Path) -> None:
    """Verify that mpt backward time.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    path = _mpt(
        tmp_path / "back.mpt", "time/s\tI/mA\tEwe/V", "0\t1\t3\n2\t1\t3\n1\t1\t3\n"
    )
    with pytest.raises(NonMonotonicTimeError):
        read(path)
