# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for api options.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

from pathlib import Path

import pytest

from battread import inspect, iter_read, read
from battread.exceptions import IncompatibleDataError, UnsupportedFormatError
from battread.readers.delimited import DelimitedReader
from battread.readers.models import ReadOptions
from battread.readers.registry import ReaderRegistry


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """Write a canonical text fixture for public reader-option validation."""
    path = tmp_path / "data.csv"
    path.write_text("Time/s,Current/mA,Voltage/V\n0,1,3\n1,2,4\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("sep", "[,;]"),
        ("sep", "\n"),
        ("decimal", ":"),
        ("encoding", ""),
        ("header", -1),
        ("header", True),
        ("skiprows", -1),
        ("skiprows", [1]),
        ("autodetect", 1),
        ("capacity_kind", "generic_capacity"),
        ("capacity_interval", "middle"),
    ],
)
def test_invalid_read_options_raise_domain_error(
    source: Path, keyword: str, value: object
) -> None:
    """Verify that invalid read options raise domain error.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError):
        read(source, **{keyword: value})  # type: ignore[arg-type]


def test_capacity_kind_requires_explicit_capacity_mapping(source: Path) -> None:
    """Verify that capacity kind requires explicit capacity mapping.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError, match=r"columns\['capacity'\]"):
        read(source, capacity_kind="cumulative_signed")


@pytest.mark.parametrize("chunk_size", [0, -1, True, 1.5])
def test_invalid_chunk_size_raises_domain_error(
    source: Path, chunk_size: object
) -> None:
    """Verify that invalid chunk size raises domain error.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError, match="positive integer"):
        iter_read(source, chunk_size=chunk_size)  # type: ignore[arg-type]


def test_unknown_reader_is_rejected(source: Path) -> None:
    """Verify that unknown reader is rejected.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(UnsupportedFormatError, match="Unknown reader"):
        inspect(source, reader="imaginary")


def test_reader_aliases_select_delimited(source: Path) -> None:
    """Verify that reader aliases select delimited.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    assert inspect(source, reader="csv").reader == "delimited"
    assert inspect(source, reader="txt").reader == "delimited"
    assert inspect(source, reader="generic").reader == "delimited"


def test_invalid_mapping_keys_and_values(source: Path) -> None:
    """Verify that invalid mapping keys and values.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError, match="column key"):
        read(source, columns={"temperature": 0})
    with pytest.raises(IncompatibleDataError, match="selector"):
        read(source, columns={"time": True})  # type: ignore[dict-item]
    with pytest.raises(IncompatibleDataError, match="cannot be empty"):
        read(source, columns={"time": ""})
    with pytest.raises(IncompatibleDataError, match="unit key"):
        read(source, units={"temperature": "K"})
    with pytest.raises(IncompatibleDataError, match="nonempty"):
        read(source, units={"time": ""})


def test_missing_source_path_is_rejected(tmp_path: Path) -> None:
    """Verify that missing source path is rejected.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    with pytest.raises(IncompatibleDataError, match="does not exist"):
        read(tmp_path / "missing.csv")


def test_explicit_reader_still_rejects_incompatible_binary(tmp_path: Path) -> None:
    """Verify that explicit reader still rejects incompatible binary.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "binary.bin"
    source.write_bytes(b"\x00\x01\x02")
    with pytest.raises(UnsupportedFormatError, match="cannot safely interpret"):
        inspect(source, reader="delimited")


def test_reader_registry_rejects_duplicate_names() -> None:
    """Verify that reader registry rejects duplicate names.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    registry = ReaderRegistry()
    registry.register(DelimitedReader())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(DelimitedReader())


def test_read_options_defaults_are_independent_empty_mappings() -> None:
    """Verify that read options defaults are independent empty mappings.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    first = ReadOptions()
    second = ReadOptions()
    assert first.columns == second.columns == {}
    assert first.units == second.units == {}
