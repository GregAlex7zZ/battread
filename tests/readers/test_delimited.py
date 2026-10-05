# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for delimited.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

import math
import warnings
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest

from battread import detect_format, inspect, iter_read, read
from battread._pandas import numpy_values
from battread.exceptions import (
    AmbiguousColumnError,
    CorruptedFileError,
    CurrentReconstructionError,
    IncompatibleDataError,
    InvalidUnitError,
    MissingColumnError,
    NonMonotonicTimeError,
    UnknownUnitError,
    UnsupportedFormatError,
)
from battread.warnings import MalformedValueWarning, MissingValueWarning


def _write(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Write a text fixture with controlled delimiters, encoding and malformed rows."""
    path.write_text(text, encoding=encoding, newline="")
    return path


def test_comma_csv_is_detected_and_standardized(tmp_path: Path) -> None:
    """Verify that comma csv is detected and standardized.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "data.csv",
        "Time/s,Current (mA),Voltage (V)\n10,1,3.2\n11,-2,3.1\n",
    )
    information = detect_format(source)
    result = read(source)

    assert information.format == "csv"
    assert information.reader == "delimited"
    assert list(result.columns) == ["time_s", "current_mA", "voltage_V"]
    assert result.dtypes.tolist() == [np.dtype("float64")] * 3
    np.testing.assert_allclose(
        numpy_values(result), [[0.0, 1.0, 3.2], [1.0, -2.0, 3.1]]
    )


def test_semicolon_decimal_comma_and_scaled_units(tmp_path: Path) -> None:
    """Verify that semicolon decimal comma and scaled units.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "data.txt",
        "Elapsed Time (ms);Current (A);Potential (mV)\n"
        "1000,0;0,001;3700,0\n2000,0;-0,002;3600,0\n",
    )
    info = inspect(source)
    result = read(source)

    assert info.delimiter == ";"
    assert info.decimal_separator == ","
    assert [match.unit for match in info.columns] == ["ms", "A", "mV"]
    np.testing.assert_allclose(
        numpy_values(result), [[0.0, 1.0, 3.7], [1.0, -2.0, 3.6]]
    )


@pytest.mark.parametrize("separator", ["\t", "whitespace"])
def test_tab_and_whitespace_delimiters(tmp_path: Path, separator: str) -> None:
    """Verify that tab and whitespace delimiters.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    actual = "\t" if separator == "\t" else "   "
    source = _write(
        tmp_path / "data.txt",
        actual.join(["Time/s", "Current/mA", "Voltage/V"])
        + "\n"
        + actual.join(["0", "1", "3.0"])
        + "\n"
        + actual.join(["2", "-1", "4.0"])
        + "\n",
    )
    result = read(source, sep=separator)
    np.testing.assert_allclose(result["time_s"], [0.0, 2.0])


def test_headerless_positional_mapping_retains_first_row(tmp_path: Path) -> None:
    """Verify that headerless positional mapping retains first row.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(tmp_path / "data.txt", "10 1 3.2\n11 2 3.3\n")
    options = {
        "header": None,
        "columns": {"time": 0, "current": 1, "voltage": 2},
        "units": {"time": "s", "current": "mA", "voltage": "V"},
    }
    result = read(source, **options)  # type: ignore[arg-type]
    assert len(result) == 2
    np.testing.assert_allclose(result["time_s"], [0.0, 1.0])


def test_explicit_options_override_detection_and_count_physical_skiprows(
    tmp_path: Path,
) -> None:
    """Verify that explicit options override detection and count physical skiprows.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "preamble.csv",
        "metadata\n\nignored;record\n\nTime/s;Current/mA;Voltage/V\n5;1;3\n6;2;4\n",
    )
    info = inspect(
        source,
        sep=";",
        decimal=".",
        encoding="utf-8",
        skiprows=2,
        header=1,
    )
    result = read(
        source,
        sep=";",
        decimal=".",
        encoding="utf-8",
        skiprows=2,
        header=1,
    )

    assert info.delimiter == ";"
    assert [match.source_column for match in info.columns] == [
        "Time/s",
        "Current/mA",
        "Voltage/V",
    ]
    np.testing.assert_allclose(result["time_s"], [0.0, 1.0])


def test_cp1252_is_detected_strictly(tmp_path: Path) -> None:
    """Verify that cp1252 is detected strictly.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "alternate.txt",
        "Durée;Courant;Tension\n0;1;3,2\n1;2;3,3\n",
        encoding="cp1252",
    )
    columns = {"time": "Durée", "current": "Courant", "voltage": "Tension"}
    units = {"time": "s", "current": "mA", "voltage": "V"}
    info = inspect(
        source,
        sep=";",
        columns=columns,
        units=units,
    )
    result = read(source, sep=";", columns=columns, units=units)
    assert info.encoding == "cp1252"
    np.testing.assert_allclose(result["voltage_V"], [3.2, 3.3])


def test_partial_explicit_mapping_overrides_negative_evidence(tmp_path: Path) -> None:
    """Verify that partial explicit mapping overrides negative evidence.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "applied.csv",
        "Time/s,Applied Current (mA),Voltage/V\n0,1,3\n1,2,4\n",
    )
    result = read(source, columns={"current": "Applied Current (mA)"})
    np.testing.assert_allclose(result["current_mA"], [1.0, 2.0])


def test_autodetect_false_requires_complete_explicit_information(
    tmp_path: Path,
) -> None:
    """Verify that autodetect false requires complete explicit information.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "data.csv", "Time/s,Current/mA,Voltage/V\n0,1,3\n1,2,4\n"
    )
    with pytest.raises(MissingColumnError, match="explicit column mapping"):
        read(source, autodetect=False)

    result = read(
        source,
        autodetect=False,
        columns={"time": 0, "current": 1, "voltage": 2},
        units={"time": "s", "current": "mA", "voltage": "V"},
    )
    assert len(result) == 2


def test_duplicate_names_require_positional_mapping(tmp_path: Path) -> None:
    """Verify that duplicate names require positional mapping.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "duplicate.csv",
        "Time/s,Current/mA,Current/mA,Voltage/V\n0,1,9,3\n1,2,8,4\n",
    )
    with pytest.raises(AmbiguousColumnError, match="use a positional mapping"):
        read(source, columns={"current": "Current/mA"})

    result = read(source, columns={"current": 2})
    np.testing.assert_allclose(result["current_mA"], [9.0, 8.0])


def test_inspect_returns_ambiguity_while_read_fails(tmp_path: Path) -> None:
    """Verify that inspect returns ambiguity while read fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "ambiguous.csv",
        "Time/s,Current/mA,Cell Voltage (V),Reference Voltage (V)\n0,1,3,4\n1,2,3,4\n",
    )
    info = inspect(source)
    voltage_matches = [match for match in info.columns if match.quantity == "voltage"]
    assert {match.state for match in voltage_matches} == {"ambiguous"}
    with pytest.raises(AmbiguousColumnError):
        read(source)


def test_unresolved_required_quantity_remains_inspectable(tmp_path: Path) -> None:
    """Verify that unresolved required quantity remains inspectable.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(tmp_path / "missing.csv", "Time/s,Voltage/V\n0,3\n1,4\n")
    info = inspect(source)
    assert not any(match.quantity == "current" for match in info.columns)
    with pytest.raises(MissingColumnError, match="current"):
        read(source)


def test_malformed_numeric_cell_is_retained_and_warned(tmp_path: Path) -> None:
    """Verify that malformed numeric cell is retained and warned.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "malformed.csv",
        "Time/s,Current/mA,Voltage/V\n0,1,3\n1,bad,4\n2,2,5\n",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = read(source)
    assert math.isnan(cast(float, result.loc[1, "current_mA"]))
    malformed = [
        item.message
        for item in caught
        if isinstance(item.message, MalformedValueWarning)
    ]
    missing = [
        item.message for item in caught if isinstance(item.message, MissingValueWarning)
    ]
    assert malformed[0].affected_counts == {"current_mA": 1}
    assert missing[0].affected_counts == {"current_mA": 1}


@pytest.mark.parametrize(
    "bad_row",
    ["1,2", "1,2,3,4"],
)
def test_structurally_malformed_row_fails(tmp_path: Path, bad_row: str) -> None:
    """Verify that structurally malformed row fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "broken.csv",
        f"Time/s,Current/mA,Voltage/V\n0,1,3\n{bad_row}\n",
    )
    with pytest.raises(CorruptedFileError, match="identity cannot be preserved"):
        read(source)


def test_wrong_extension_with_recognizable_content_is_supported(tmp_path: Path) -> None:
    """Verify that wrong extension with recognizable content is supported.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "data.dat", "Time/s,Current/mA,Voltage/V\n0,1,3\n1,2,4\n"
    )
    assert detect_format(source).reader == "delimited"
    assert len(read(source)) == 2


def test_invalid_binary_content_is_unsupported(tmp_path: Path) -> None:
    """Verify that invalid binary content is unsupported.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "data.bin"
    source.write_bytes(b"\x00\x01\x02\xff")
    with pytest.raises(UnsupportedFormatError):
        detect_format(source)


def test_explicit_encoding_decodes_strictly(tmp_path: Path) -> None:
    """Verify that explicit encoding decodes strictly.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = tmp_path / "data.csv"
    source.write_bytes("Durée,Current/mA,Voltage/V\n0,1,3\n1,2,4\n".encode("cp1252"))
    with pytest.raises(CorruptedFileError, match="strictly"):
        inspect(source, encoding="utf-8")


@pytest.mark.parametrize("chunk_size", [1, 2, 3, 10])
def test_chunked_and_complete_direct_read_are_equivalent(
    tmp_path: Path, chunk_size: int
) -> None:
    """Verify that chunked and complete direct read are equivalent.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "chunks.csv",
        "Time/s,Current (A),Voltage (mV)\n"
        "10,0.001,3000\n11,-0.002,3100\n11,0,3200\n13,0.004,3300\n",
    )
    expected = read(source)
    actual = pd.concat(iter_read(source, chunk_size=chunk_size), ignore_index=True)
    pd.testing.assert_frame_equal(actual, expected)
    assert all(
        len(chunk) <= chunk_size for chunk in iter_read(source, chunk_size=chunk_size)
    )


def test_time_origin_and_monotonicity_are_stateful_across_chunks(
    tmp_path: Path,
) -> None:
    """Verify that time origin and monotonicity are stateful across chunks.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "time.csv",
        "Time/s,Current/mA,Voltage/V\n,1,3\n10,2,4\n9,3,5\n",
    )
    iterator = iter_read(source, chunk_size=1)
    with pytest.warns(MissingValueWarning):
        first = next(iterator)
    second = next(iterator)
    assert math.isnan(cast(float, first.loc[0, "time_s"]))
    assert second.loc[0, "time_s"] == 0.0
    with pytest.raises(NonMonotonicTimeError):
        next(iterator)


def test_iter_read_can_fail_at_end_when_time_is_entirely_missing(
    tmp_path: Path,
) -> None:
    """Verify that iter read can fail at end when time is entirely missing.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "missing-time.csv",
        "Time/s,Current/mA,Voltage/V\n,1,3\n,2,4\n",
    )
    iterator = iter_read(source, chunk_size=1)
    with pytest.warns(MissingValueWarning):
        next(iterator)
    with pytest.warns(MissingValueWarning):
        next(iterator)
    with pytest.raises(IncompatibleDataError, match="no finite value"):
        next(iterator)


def test_capacity_is_inspectable_but_not_reconstructed_in_this_milestone(
    tmp_path: Path,
) -> None:
    """Verify that capacity is inspectable but not reconstructed in this milestone.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "capacity.csv",
        "Time/s,Capacity (mAh),Voltage/V\n0,0,3\n1,1,4\n",
    )
    info = inspect(source)
    assert any(match.semantic == "generic_capacity" for match in info.columns)
    assert info.current_reconstruction_required is None
    with pytest.raises(CurrentReconstructionError):
        read(source)


def test_direct_current_precedes_explicit_capacity_options(tmp_path: Path) -> None:
    """Verify that direct current precedes explicit capacity options.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "direct.csv",
        "Time/s,Current/mA,Capacity (mAh),Voltage/V\n0,,0,3\n1,,1,4\n",
    )
    with pytest.warns(MissingValueWarning) as caught:
        result = read(
            source,
            columns={"capacity": "Capacity (mAh)"},
            capacity_kind="cumulative_signed",
            capacity_interval="next",
        )
    assert all(result["current_mA"].isna())
    message = caught[0].message
    assert isinstance(message, MissingValueWarning)
    assert message.affected_counts == {"current_mA": 2}


def test_explicit_unit_override_resolves_unsupported_header_notation(
    tmp_path: Path,
) -> None:
    """Verify that explicit unit override resolves unsupported header notation.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "units.csv",
        "Time (Ms),Current (MA),Voltage (V)\n1000,1,3\n2000,2,4\n",
    )
    result = read(source, units={"time": "ms", "current": "mA"})
    np.testing.assert_allclose(result["time_s"], [0.0, 1.0])
    np.testing.assert_allclose(result["current_mA"], [1.0, 2.0])


def test_missing_voltage_is_reported_before_capacity_fallback(tmp_path: Path) -> None:
    """Verify that missing voltage is reported before capacity fallback.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "missing-voltage.csv",
        "Time/s,Capacity (mAh)\n0,0\n1,1\n",
    )
    with pytest.raises(MissingColumnError, match="voltage"):
        read(source)


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
def test_bom_encodings_are_detected(tmp_path: Path, encoding: str) -> None:
    """Verify that bom encodings are detected.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "bom.csv",
        "Time/s,Current/mA,Voltage/V\n0,1,3\n1,2,4\n",
        encoding=encoding,
    )
    info = inspect(source)
    assert info.encoding == encoding
    assert len(read(source)) == 2


def test_unknown_encoding_name_is_rejected(tmp_path: Path) -> None:
    """Verify that unknown encoding name is rejected.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(tmp_path / "data.csv", "Time/s,Current/mA,Voltage/V\n0,1,3\n")
    with pytest.raises(IncompatibleDataError, match="Unknown text encoding"):
        inspect(source, encoding="not-a-real-codec")


def test_empty_and_exhausted_sources_fail_explicitly(tmp_path: Path) -> None:
    """Verify that empty and exhausted sources fail explicitly.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    empty = _write(tmp_path / "empty.csv", "")
    with pytest.raises(IncompatibleDataError, match="empty"):
        read(empty)

    skipped = _write(tmp_path / "skipped.csv", "Time/s,Current/mA,Voltage/V\n0,1,3\n")
    with pytest.raises(IncompatibleDataError, match="after skiprows"):
        read(skipped, skiprows=10)


def test_uncertain_header_requires_override(tmp_path: Path) -> None:
    """Verify that uncertain header requires override.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(tmp_path / "uncertain.txt", "alpha,beta,gamma\none,two,three\n")
    with pytest.raises(IncompatibleDataError, match="Header presence is uncertain"):
        inspect(source, sep=",")


def test_invalid_header_and_single_column_fail_safely(tmp_path: Path) -> None:
    """Verify that invalid header and single column fail safely.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(tmp_path / "data.csv", "Time/s,Current/mA,Voltage/V\n0,1,3\n")
    with pytest.raises(IncompatibleDataError, match="Header record 5"):
        inspect(source, sep=",", header=5)

    single = _write(tmp_path / "single.txt", "Value\n1\n2\n")
    with pytest.raises(IncompatibleDataError, match="multiple columns"):
        inspect(single, sep=",", header=0)


def test_explicit_mapping_missing_or_out_of_range_fails(tmp_path: Path) -> None:
    """Verify that explicit mapping missing or out of range fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(tmp_path / "data.csv", "Time/s,Current/mA,Voltage/V\n0,1,3\n")
    with pytest.raises(MissingColumnError, match="was not found"):
        read(source, columns={"current": "missing"})
    with pytest.raises(MissingColumnError, match="outside"):
        read(source, columns={"current": 9})


def test_one_source_position_cannot_have_two_semantics(tmp_path: Path) -> None:
    """Verify that one source position cannot have two semantics.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(tmp_path / "data.csv", "Time/s,Current/mA,Voltage/V\n0,1,3\n")
    with pytest.raises(IncompatibleDataError, match="mapped to both"):
        inspect(source, columns={"time": 0, "current": 0})


def test_missing_or_incompatible_units_fail_explicitly(tmp_path: Path) -> None:
    """Verify that missing or incompatible units fail explicitly.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(tmp_path / "units.csv", "Time,Current,Voltage\n0,1,3\n1,2,4\n")
    with pytest.raises(UnknownUnitError, match=r"units=.*time"):
        read(source)
    with pytest.raises(InvalidUnitError):
        read(source, units={"time": "s", "current": "V", "voltage": "V"})


@pytest.mark.parametrize(
    ("column", "value"),
    [("time_s", "inf"), ("current_mA", "inf"), ("voltage_V", "-inf")],
)
def test_infinity_in_canonical_quantity_fails(
    tmp_path: Path, column: str, value: str
) -> None:
    """Verify that infinity in canonical quantity fails.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    row = {"time_s": "0", "current_mA": "1", "voltage_V": "3"}
    row[column] = value
    source = _write(
        tmp_path / "infinite.csv",
        "time_s,current_mA,voltage_V\n"
        f"{row['time_s']},{row['current_mA']},{row['voltage_V']}\n",
    )
    with pytest.raises(IncompatibleDataError, match="infinite"):
        read(source)


def test_explicit_decimal_comma_rejects_decimal_point_cells(tmp_path: Path) -> None:
    """Verify that explicit decimal comma rejects decimal point cells.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "mixed.txt",
        "Time/s;Current/mA;Voltage/V\n0;1.5;3,0\n1;2,5;4,0\n",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = read(source, sep=";", decimal=",")
    assert math.isnan(cast(float, result.loc[0, "current_mA"]))
    assert any(isinstance(item.message, MalformedValueWarning) for item in caught)


def test_capacity_pair_units_apply_to_matching_semantics(tmp_path: Path) -> None:
    """Verify that capacity pair units apply to matching semantics.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "capacity.txt",
        "Time/s;Charge Capacity;Discharge Capacity;Voltage/V\n0;0;0;3\n1;1;0;4\n",
    )
    info = inspect(
        source,
        sep=";",
        units={"charge_capacity": "Ah", "discharge_capacity": "mAh"},
    )
    capacities = [match for match in info.columns if match.quantity == "capacity"]
    assert [(match.semantic, match.unit) for match in capacities] == [
        ("charge_capacity", "Ah"),
        ("discharge_capacity", "mAh"),
    ]
    assert info.current_reconstruction_required is True


def test_warning_totals_are_chunk_size_invariant(tmp_path: Path) -> None:
    """Verify that warning totals are chunk size invariant.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "warnings.csv",
        "Time/s,Current/mA,Voltage/V\n0,1,3\n1,bad,\n2,,5\n3,4,6\n",
    )

    def totals(chunk_size: int) -> tuple[dict[str, int], dict[str, int]]:
        """Collect missing-value warning counts to compare streamed and full reads."""
        missing: dict[str, int] = {}
        malformed: dict[str, int] = {}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            list(iter_read(source, chunk_size=chunk_size))
        for item in caught:
            if isinstance(item.message, MissingValueWarning):
                for key, count in item.message.affected_counts.items():
                    missing[key] = missing.get(key, 0) + count
            if isinstance(item.message, MalformedValueWarning):
                for key, count in item.message.affected_counts.items():
                    malformed[key] = malformed.get(key, 0) + count
        return missing, malformed

    assert (
        totals(1)
        == totals(2)
        == totals(10)
        == (
            {"current_mA": 2, "voltage_V": 1},
            {"current_mA": 1},
        )
    )


def test_parsing_options_are_shared_by_iter_read(tmp_path: Path) -> None:
    """Verify that parsing options are shared by iter read.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "preamble.txt",
        "metadata\nTime/s;Current/mA;Voltage/V\n10;1;3\n11;2;4\n",
    )
    chunks = list(
        iter_read(
            source,
            chunk_size=1,
            sep=";",
            decimal=".",
            encoding="utf-8",
            skiprows=1,
            header=0,
        )
    )
    assert [chunk.loc[0, "time_s"] for chunk in chunks] == [0.0, 1.0]


def test_ambiguous_current_keeps_inspection_strategy_unknown(tmp_path: Path) -> None:
    """Verify that ambiguous current keeps inspection strategy unknown.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "ambiguous-current.csv",
        "Time/s,Current 1 (mA),Current 2 (mA),Voltage/V\n0,1,2,3\n1,2,3,4\n",
    )
    info = inspect(source)
    assert info.current_reconstruction_required is None
    with pytest.raises(AmbiguousColumnError):
        read(source)


def test_explicit_capacity_mapping_records_both_pair_semantics(tmp_path: Path) -> None:
    """Verify that explicit capacity mapping records both pair semantics.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    source = _write(
        tmp_path / "capacities.csv",
        "Time/s,Q1,Q2,Voltage/V\n0,0,0,3\n1,1,0,4\n",
    )
    info = inspect(
        source,
        columns={"charge_capacity": "Q1", "discharge_capacity": "Q2"},
        units={"charge_capacity": "mAh", "discharge_capacity": "mAh"},
    )
    assert [match.semantic for match in info.columns[1:3]] == [
        "charge_capacity",
        "discharge_capacity",
    ]
    assert all(match.state == "explicit" for match in info.columns[1:3])


def test_header_without_data_and_malformed_quotes_fail(tmp_path: Path) -> None:
    """Verify that header without data and malformed quotes fail.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    header_only = _write(tmp_path / "header.csv", "Time/s,Current/mA,Voltage/V\n")
    with pytest.raises(IncompatibleDataError, match="header but no data"):
        inspect(header_only, sep=",", header=0)

    malformed = _write(
        tmp_path / "quotes.csv",
        'Time/s,Current/mA,Voltage/V\n0,"unterminated,3\n',
    )
    with pytest.raises(CorruptedFileError, match="Malformed delimited text"):
        inspect(malformed, sep=",")


def test_late_malformed_csv_record_fails_during_streaming(tmp_path: Path) -> None:
    """Verify that late malformed csv record fails during streaming.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    rows = ["Time/s,Current/mA,Voltage/V"]
    rows.extend(f"{index},{index},3" for index in range(90))
    rows.append('91,"unterminated,3')
    source = _write(tmp_path / "late.csv", "\n".join(rows) + "\n")
    iterator = iter_read(source, chunk_size=20)
    assert sum(len(next(iterator)) for _ in range(4)) == 80
    with pytest.raises(CorruptedFileError, match="Malformed delimited record"):
        list(iterator)
