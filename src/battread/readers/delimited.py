# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Streaming generic CSV and TXT reader."""

import codecs
import csv
import math
import re
import warnings
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from battread._pandas import numeric_values
from battread.constants import (
    CANONICAL_COLUMNS,
    CURRENT_COLUMN,
    TIME_COLUMN,
    VOLTAGE_COLUMN,
)
from battread.exceptions import (
    AmbiguousColumnError,
    CorruptedFileError,
    CurrentReconstructionError,
    IncompatibleDataError,
    MissingColumnError,
    UnknownUnitError,
)
from battread.normalization.units import (
    Quantity,
    conversion_factor,
    identify_unit,
)
from battread.readers.models import (
    FormatInfo,
    ReaderCapabilities,
    ReadOptions,
    SemanticKey,
)
from battread.recognition import parse_label, recognize_columns, resolve_quantity
from battread.recognition.models import (
    CapacitySemantic,
    ColumnMatch,
    InspectionResult,
    KnownQuantity,
    ReaderHint,
)
from battread.reconstruction import CurrentReconstructor
from battread.validation import validate_standardized
from battread.warnings import MalformedValueWarning, MissingValueWarning

_SAMPLE_BYTES = 131_072
_SAMPLE_RECORDS = 80
_DEFAULT_READ_CHUNK = 250_000
_SEPARATORS = (",", ";", "\t", "whitespace")


@dataclass(frozen=True, slots=True)
class _TablePlan:
    """Describe validated text structure independently of scientific column choices.

    encoding, separator and decimal control parsing; header_record counts
    nonblank records after skiprows. columns preserve duplicates and width
    protects row identity. canonical marks the exact library schema, whose
    existing time origin must be checked instead of repaired.
    """

    encoding: str
    separator: str
    decimal: str
    header_record: int | None
    columns: tuple[str | int, ...]
    width: int
    canonical: bool


@dataclass(frozen=True, slots=True)
class _Selection:
    """Bind a semantic key to an original source position and verified unit.

    Numeric conversion uses positions so duplicate labels cannot collapse
    into one column. This is produced only after recognition or explicit selection.
    """

    key: Quantity
    position: int
    unit: str


def _decode_prefix(path: Path, requested: str | None) -> tuple[str, str]:
    """Inspect bounded bytes to choose a strict text decoder, not load the file.

    Return (encoding, decoded_prefix). An explicit codec takes precedence;
    otherwise BOM, UTF-8 and the supported alternate encoding are checked.
    Reject empty, undecodable or binary-looking data with package errors.
    """
    try:
        with path.open("rb") as stream:
            prefix = stream.read(_SAMPLE_BYTES)
    except OSError as error:
        raise CorruptedFileError(f"Unable to read {path}: {error}.") from error
    if not prefix:
        raise IncompatibleDataError(f"Delimited source {path} is empty.")

    if requested is not None:
        try:
            canonical = codecs.lookup(requested).name
        except LookupError as error:
            raise IncompatibleDataError(
                f"Unknown text encoding {requested!r}."
            ) from error
        try:
            return canonical, prefix.decode(canonical, errors="strict")
        except UnicodeDecodeError as error:
            raise CorruptedFileError(
                f"Source cannot be decoded strictly as {requested!r}."
            ) from error

    candidates: tuple[str, ...]
    if prefix.startswith(codecs.BOM_UTF8):
        candidates = ("utf-8-sig",)
    elif prefix.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        candidates = ("utf-16",)
    else:
        candidates = ("utf-8", "cp1252")
    for encoding in candidates:
        try:
            text = prefix.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
        controls = sum(
            character < " " and character not in "\r\n\t" for character in text
        )
        if "\x00" not in text and controls <= max(1, len(text) // 1000):
            return encoding, text
    raise CorruptedFileError(
        "Source is not valid supported text. Provide an explicit encoding if known."
    )


def _sample_physical_lines(
    path: Path, encoding: str, *, skiprows: int, minimum: int
) -> list[str]:
    """Sample physical lines after the explicit skipped prefix for dialect planning.

    Decode strictly and stop at minimum sampled lines. Sampling is reopened
    for actual reading, so it cannot consume scientific rows. Wrap read/decode
    failures as CorruptedFileError.
    """
    lines: list[str] = []
    try:
        with path.open("r", encoding=encoding, errors="strict", newline="") as stream:
            for _ in range(skiprows):
                if stream.readline() == "":
                    break
            for line in stream:
                lines.append(line.rstrip("\r\n"))
                if len(lines) >= minimum:
                    break
    except (OSError, UnicodeDecodeError) as error:
        raise CorruptedFileError(f"Unable to decode {path} safely: {error}.") from error
    return lines


def _parse_sample(lines: Sequence[str], separator: str) -> list[list[str]]:
    """Parse nonblank sample records with a candidate literal delimiter.

    Whitespace mode splits spaces/tabs; other modes use strict CSV quoting.
    This returns rows for structural inference only, never scientific decisions.
    """
    nonblank = [line for line in lines if line.strip()]
    if separator == "whitespace":
        return [re.split(r"[ \t]+", line.strip()) for line in nonblank]
    try:
        return list(csv.reader(nonblank, delimiter=separator, strict=True))
    except csv.Error as error:
        raise CorruptedFileError(f"Malformed delimited text: {error}.") from error


def _as_number(value: str, decimal: str) -> float | None:
    """Try one sample cell under a candidate decimal convention.

    Return float or None for empty/unparseable cells. Decimal comma rejects
    embedded decimal points; this helper scores structure and does not silently
    remove malformed cells during real ingestion.
    """
    text = value.strip()
    if not text:
        return None
    if decimal == ",":
        if text.count(",") > 1 or "." in text:
            return None
        text = text.replace(",", ".")
    try:
        result = float(text)
    except ValueError:
        return None
    return result


def _numeric_fraction(row: Sequence[str], decimal: str) -> float:
    """Measure numeric-looking cells in a sample row for header/dialect scoring.

    Return zero for an empty row. The score is structural evidence only;
    column meaning is established separately by the recognition engine.
    """
    if not row:
        return 0.0
    return sum(_as_number(value, decimal) is not None for value in row) / len(row)


def _likely_header(rows: Sequence[Sequence[str]], decimal: str) -> bool | None:
    """Infer header presence conservatively from sampled numeric and label evidence.

    Return True, False or None for uncertainty. A None result requires an
    explicit header option instead of risking omission of the first data row.
    """
    if len(rows) < 2:
        return None
    first = _numeric_fraction(rows[0], decimal)
    following = sum(_numeric_fraction(row, decimal) for row in rows[1:6]) / min(
        5, len(rows) - 1
    )
    if first >= 0.75:
        return False
    if first <= 0.25 and following >= 0.5:
        return True
    matches = recognize_columns(rows[0])
    recognized = sum(match.quantity != "unknown" for match in matches)
    if recognized >= 2 and following >= 0.25:
        return True
    return None


def _detect_decimal(rows: Sequence[Sequence[str]], header_record: int | None) -> str:
    """Choose point or comma using numeric sample cells after the header.

    Compare supported interpretations and prefer point on equal scores.
    Explicit decimal options bypass this structural inference.
    """
    data = rows[(header_record + 1 if header_record is not None else 0) :]
    cells = [cell.strip() for row in data[:20] for cell in row if cell.strip()]
    comma = sum(_as_number(cell, ",") is not None for cell in cells)
    point = sum(_as_number(cell, ".") is not None for cell in cells)
    if comma > point:
        return ","
    return "."


def _delimiter_score(rows: Sequence[Sequence[str]]) -> float | None:
    """Score a candidate table using consistent widths and numeric-looking cells.

    Return None for insufficient multi-column evidence. Width consistency
    helps separate delimiters from decimal punctuation; actual reading still
    checks every record's width and never drops mismatched scientific rows.
    """
    if len(rows) < 2:
        return None
    widths = [len(row) for row in rows[:20]]
    modal_width = max(set(widths), key=widths.count)
    consistent = [row for row in rows[:20] if len(row) == modal_width]
    if modal_width <= 1 or len(consistent) < 2:
        return None
    best_numeric = 0.0
    for decimal in (".", ","):
        header = _likely_header(consistent, decimal)
        start = 1 if header else 0
        fractions = [_numeric_fraction(row, decimal) for row in consistent[start:20]]
        if fractions:
            best_numeric = max(best_numeric, sum(fractions) / len(fractions))
    consistency = len(consistent) / min(20, len(rows))
    return 10.0 * best_numeric + min(modal_width, 10) + consistency


def _detect_separator(lines: Sequence[str]) -> str:
    """Select a unique supported delimiter from bounded sample evidence.

    A tab/whitespace tie is resolved only by actual tabs in the sample. Other
    ties or absent evidence raise IncompatibleDataError requesting explicit sep.
    """
    scored: list[tuple[float, str]] = []
    for separator in _SEPARATORS:
        rows = _parse_sample(lines, separator)
        score = _delimiter_score(rows)
        if score is not None:
            scored.append((score, separator))
    if not scored:
        raise IncompatibleDataError(
            "Could not determine a safe delimiter; provide sep explicitly."
        )
    scored.sort(reverse=True)
    best_score = scored[0][0]
    winners = [separator for score, separator in scored if score == best_score]
    if set(winners) == {"\t", "whitespace"} and any("\t" in line for line in lines):
        return "\t"
    if len(winners) > 1:
        raise IncompatibleDataError(
            "Delimited structure is ambiguous; provide sep explicitly."
        )
    return winners[0]


def _make_plan(path: Path, options: ReadOptions) -> _TablePlan:
    """Resolve text structure once so inspection and ingestion use the same rules.

    Apply explicit options before inference, preserving headerless positions
    and duplicate names. Return _TablePlan; uncertain header/dialect, absent
    records or unsafe widths fail before choosing scientific columns.
    """
    encoding, _ = _decode_prefix(path, options.encoding)
    minimum = max(
        _SAMPLE_RECORDS, (options.header + 10) if isinstance(options.header, int) else 0
    )
    lines = _sample_physical_lines(
        path, encoding, skiprows=options.skiprows, minimum=minimum
    )
    if not any(line.strip() for line in lines):
        raise IncompatibleDataError("No table records remain after skiprows.")
    separator = options.sep or _detect_separator(lines)
    rows = _parse_sample(lines, separator)
    if not rows:
        raise IncompatibleDataError("No nonblank table records were found.")

    if options.header == "infer":
        provisional_decimal = options.decimal or _detect_decimal(rows, None)
        inferred = _likely_header(rows, provisional_decimal)
        if inferred is None:
            raise IncompatibleDataError(
                "Header presence is uncertain; provide header=0 or header=None."
            )
        header_record = 0 if inferred else None
    else:
        header_record = options.header

    if header_record is not None and header_record >= len(rows):
        raise IncompatibleDataError(
            f"Header record {header_record} was not found after skiprows."
        )
    first_data = header_record + 1 if header_record is not None else 0
    if first_data >= len(rows):
        raise IncompatibleDataError("The source contains a header but no data rows.")
    width = len(rows[header_record] if header_record is not None else rows[first_data])
    if width < 2:
        raise IncompatibleDataError(
            "Delimited source does not contain multiple columns."
        )
    columns: tuple[str | int, ...]
    if header_record is None:
        columns = tuple(range(width))
    else:
        columns = tuple(cell.strip() for cell in rows[header_record])
    decimal = options.decimal or _detect_decimal(rows, header_record)
    return _TablePlan(
        encoding,
        separator,
        decimal,
        header_record,
        columns,
        width,
        columns == CANONICAL_COLUMNS,
    )


def _position_for_selector(
    columns: Sequence[str | int], selector: str | int, key: SemanticKey
) -> int:
    """Resolve a name or zero-based position to exactly one original column.

    Reject out-of-range positions, missing names and duplicated name matches.
    This prevents an explicit mapping from silently selecting the wrong sibling.
    """
    if isinstance(selector, int):
        if selector < 0 or selector >= len(columns):
            raise MissingColumnError(
                f"Explicit {key} position {selector} is outside the source schema."
            )
        return selector
    positions = [index for index, column in enumerate(columns) if column == selector]
    if not positions:
        raise MissingColumnError(f"Explicit {key} column {selector!r} was not found.")
    if len(positions) > 1:
        raise AmbiguousColumnError(
            f"Explicit {key} name {selector!r} matches positions {positions}; "
            "use a positional mapping."
        )
    return positions[0]


def _explicit_semantic(
    key: SemanticKey, options: ReadOptions
) -> CapacitySemantic | None:
    """Determine capacity meaning for an explicit selector and declared options.

    Charge/discharge keys establish their respective pair roles. A generic
    capacity selector needs capacity_kind; its position alone supplies no science.
    """
    if key == "capacity":
        return options.capacity_kind or "generic_capacity"
    if key == "charge_capacity":
        return "charge_capacity"
    if key == "discharge_capacity":
        return "discharge_capacity"
    return None


def _quantity_for_key(key: SemanticKey) -> KnownQuantity:
    """Map charge/discharge selector keys to the shared capacity quantity.

    Other validated keys already name their quantity. Use for unit checks
    without losing the selector's separate capacity semantics.
    """
    if key in {"capacity", "charge_capacity", "discharge_capacity"}:
        return "capacity"
    return cast(KnownQuantity, key)


def _inspection_matches(
    plan: _TablePlan,
    options: ReadOptions,
    *,
    vendor: str | None = None,
    hints: Sequence[ReaderHint] = (),
    prefer_total_time: bool = False,
) -> tuple[ColumnMatch, ...]:
    """Combine declarative recognition, verified hints and explicit user overrides.

    Use a structural plan plus ReadOptions; return one ColumnMatch per original
    column. Preserve rejected evidence and duplicate positions. The verified
    Neware CSV profiles and the CSV paired-clock policy establish elapsed time. Apply
    explicit mappings and units last, and reject unsafe canonical overrides.
    """
    if options.autodetect:
        matches = list(recognize_columns(plan.columns, vendor=vendor, hints=hints))
        # The measurement signature establishes total elapsed vs step time.
        # Step Type is optional: some exports omit it or leave its label blank.
        # Keep the other exact labels required; generic paired clocks stay ambiguous.
        neware_export = {
            "DataPoint",
            "Time",
            "Total Time",
            "Current(mA)",
            "Voltage(V)",
            "Capacity(mAh)",
            "Energy(Wh)",
            "Date",
            "Power(W)",
        }
        if vendor is None and neware_export.issubset(plan.columns):
            for index, match in enumerate(matches):
                if match.source_column == "Total Time":
                    matches[index] = replace(
                        match,
                        quantity="time",
                        unit="s",
                        state="resolved",
                        confidence=1.0,
                        evidence=(
                            "Neware CSV export profile: total elapsed clock in seconds",
                        ),
                    )
                elif match.quantity == "time":
                    matches[index] = replace(
                        match,
                        state="unresolved",
                        evidence=(
                            *match.evidence,
                            "Neware CSV profile: step or calendar time rejected",
                        ),
                    )
        if prefer_total_time:
            labels = [parse_label(column) for column in plan.columns]
            if any(label.normalized_label == "time" for label in labels) and any(
                label.normalized_label == "total time" for label in labels
            ):
                for index, (match, label) in enumerate(
                    zip(matches, labels, strict=True)
                ):
                    if label.normalized_label == "total time":
                        # Bare Total Time is seconds by the documented CSV policy.
                        # An explicit unit is never replaced by this default.
                        unit = label.canonical_unit if label.unit_expression else "s"
                        matches[index] = replace(
                            match,
                            quantity="time",
                            unit=unit,
                            state="resolved",
                            confidence=1.0,
                            evidence=(
                                *match.evidence,
                                "CSV time preference: Total Time supersedes Time",
                            ),
                        )
                    elif label.normalized_label == "time":
                        matches[index] = replace(
                            match,
                            state="unresolved",
                            evidence=(
                                *match.evidence,
                                "CSV time preference: Time superseded by Total Time",
                            ),
                        )
    else:
        matches = [
            ColumnMatch(
                column,
                index,
                "unknown",
                None,
                None,
                None,
                "unresolved",
                0.0,
                ("automatic semantic recognition disabled",),
            )
            for index, column in enumerate(plan.columns)
        ]

    explicit_positions: dict[int, SemanticKey] = {}
    for key, selector in options.columns.items():
        position = _position_for_selector(plan.columns, selector, key)
        if position in explicit_positions:
            raise IncompatibleDataError(
                f"Source position {position} is mapped to both "
                f"{explicit_positions[position]!r} and {key!r}."
            )
        explicit_positions[position] = key

    explicit_quantities = {
        "capacity"
        if key in {"capacity", "charge_capacity", "discharge_capacity"}
        else key
        for key in explicit_positions.values()
    }
    for index, match in enumerate(matches):
        key = explicit_positions.get(index)
        if key is not None:
            quantity = _quantity_for_key(key)
            unit_key = key
            explicit_unit = options.units.get(unit_key)
            unit = match.unit
            if explicit_unit is not None:
                conversion_factor(quantity, explicit_unit)
                identified = identify_unit(explicit_unit)
                assert identified is not None
                unit = identified[1]
            matches[index] = ColumnMatch(
                match.source_column,
                match.source_position,
                quantity,
                unit,
                _explicit_semantic(key, options),
                options.capacity_interval
                if options.capacity_kind == "delta_signed"
                else None,
                "explicit",
                1.0,
                ("explicit user column mapping",),
            )
        elif match.quantity in explicit_quantities:
            matches[index] = replace(
                match,
                state="unresolved",
                evidence=(*match.evidence, "superseded by explicit mapping"),
            )

    for key, explicit_unit in options.units.items():
        if key in options.columns:
            continue
        quantity = _quantity_for_key(key)
        conversion_factor(quantity, explicit_unit)
        identified = identify_unit(explicit_unit)
        assert identified is not None
        for index, match in enumerate(matches):
            semantic_matches = (
                key not in {"charge_capacity", "discharge_capacity"}
                or match.semantic == key
            )
            if (
                match.quantity == quantity
                and semantic_matches
                and match.state in {"resolved", "ambiguous"}
            ):
                matches[index] = replace(
                    match,
                    unit=identified[1],
                    evidence=(*match.evidence, "explicit unit override"),
                )
    return tuple(matches)


def _strategy(matches: Sequence[ColumnMatch]) -> bool | None:
    """Describe whether matched fields establish direct current or reconstruction.

    Return False for usable direct semantics, True for sufficiently known
    capacity semantics, or None when a choice remains unresolved. This informs
    inspection without making missing current samples trigger reconstruction.
    """
    direct = any(
        match.quantity == "current"
        and match.state in {"resolved", "explicit"}
        and match.unit is not None
        for match in matches
    )
    ambiguous = any(
        match.quantity == "current" and match.state == "ambiguous" for match in matches
    )
    if direct:
        return False
    if ambiguous:
        return None
    capacities = [
        match
        for match in matches
        if match.quantity == "capacity"
        and match.state in {"resolved", "explicit"}
        and match.unit is not None
    ]
    semantics = {match.semantic for match in capacities}
    safe = (
        "cumulative_signed" in semantics
        or any(
            match.semantic == "delta_signed" and match.interval_alignment is not None
            for match in capacities
        )
        or {"charge_capacity", "discharge_capacity"}.issubset(semantics)
    )
    return True if safe else None


def _selection_for(
    key: Literal["time", "current", "voltage"],
    plan: _TablePlan,
    options: ReadOptions,
    matches: Sequence[ColumnMatch],
) -> _Selection:
    """Require one safe field for a quantity and validate its unit.

    Use explicit selection when supplied, otherwise resolve candidate evidence.
    Return a positional _Selection; ambiguity, absent semantics or incompatible
    units raise their domain errors rather than selecting an arbitrary column.
    """
    selector = options.columns.get(key)
    if selector is not None:
        position = _position_for_selector(plan.columns, selector, key)
        match = matches[position]
    else:
        if not options.autodetect:
            raise MissingColumnError(
                f"{key.capitalize()} requires an explicit column mapping when "
                "autodetect=False."
            )
        match = resolve_quantity(matches, key)
        position = match.source_position
    unit = options.units.get(key) or match.unit
    if unit is None:
        raise UnknownUnitError(
            f"No reliable unit was found for {key} column {match.source_column!r}; "
            f"provide units={{'{key}': ...}}."
        )
    conversion_factor(key, unit)
    return _Selection(key, position, unit)


def _iter_source_records(
    path: Path, plan: _TablePlan, skiprows: int
) -> Iterator[list[str]]:
    """Stream full-width source records without silently skipping malformed rows.

    Reopen the source, apply physical skiprows and nonblank header counting,
    and retain every data record with the expected width. Blank physical records
    are not measurements; wrong-width or invalid quoting/encoding fails because
    cell-to-column identity cannot be preserved.
    """
    try:
        with path.open(
            "r", encoding=plan.encoding, errors="strict", newline=""
        ) as stream:
            for _ in range(skiprows):
                if stream.readline() == "":
                    return
            if plan.separator == "whitespace":
                records: Iterator[list[str]] = (
                    re.split(r"[ \t]+", line.strip()) for line in stream if line.strip()
                )
            else:
                records = iter(
                    csv.reader(stream, delimiter=plan.separator, strict=True)
                )
            record_number = -1
            for row in records:
                if not row or (len(row) == 1 and not row[0].strip()):
                    continue
                record_number += 1
                if (
                    plan.header_record is not None
                    and record_number <= plan.header_record
                ):
                    continue
                if len(row) != plan.width:
                    raise CorruptedFileError(
                        f"Record {record_number} has {len(row)} fields; expected "
                        f"{plan.width}. Row identity cannot be preserved safely."
                    )
                yield row
    except UnicodeDecodeError as error:
        raise CorruptedFileError(
            f"Source cannot be decoded strictly as {plan.encoding!r}."
        ) from error
    except csv.Error as error:
        raise CorruptedFileError(f"Malformed delimited record: {error}.") from error


def _capacity_strategy(
    matches: Sequence[ColumnMatch], options: ReadOptions
) -> tuple[CurrentReconstructor, tuple[_Selection, ...]]:
    """Build reconstruction only from a safely selected capacity interpretation.

    Called after direct-current selection fails. Prefer an explicitly selected
    signed strategy over alternatives, require incremental alignment and verified
    units, or require both charge/discharge roles. Return the stateful reconstructor
    and positional capacity selections; unsupported inference fails explicitly.
    """
    candidates = [
        match
        for match in matches
        if match.quantity == "capacity" and match.state in {"resolved", "explicit"}
    ]
    explicit = "capacity" in options.columns
    signed = [
        m for m in candidates if m.semantic in {"cumulative_signed", "delta_signed"}
    ]
    if explicit:
        signed = [
            m
            for m in candidates
            if m.state == "explicit"
            and (
                m.source_column == options.columns["capacity"]
                or m.source_position == options.columns["capacity"]
            )
            and m.semantic in {"cumulative_signed", "delta_signed"}
        ]
        if not signed:
            raise CurrentReconstructionError(
                "Explicit capacity requires declared signed semantics."
            )
    if signed:
        if len(signed) != 1:
            raise AmbiguousColumnError(
                "Multiple signed capacity candidates require explicit selection."
            )
        selected = signed
        kind = cast(Literal["cumulative_signed", "delta_signed"], signed[0].semantic)
        alignment = options.capacity_interval or signed[0].interval_alignment
        if kind == "cumulative_signed" and options.capacity_interval is not None:
            raise CurrentReconstructionError(
                "Cumulative capacity does not accept interval alignment."
            )
        if kind == "delta_signed" and alignment is None:
            raise CurrentReconstructionError(
                "Incremental capacity requires previous/next alignment."
            )
        reconstructor = CurrentReconstructor(kind, alignment or "previous")
    else:
        charge = [m for m in candidates if m.semantic == "charge_capacity"]
        discharge = [m for m in candidates if m.semantic == "discharge_capacity"]
        if len(charge) > 1 or len(discharge) > 1:
            raise AmbiguousColumnError(
                "Multiple charge/discharge capacity candidates require selection."
            )
        if not charge or not discharge:
            raise CurrentReconstructionError(
                "No capacity with sufficiently established semantics is available."
            )
        if options.capacity_interval is not None:
            raise CurrentReconstructionError(
                "Cumulative capacity pairs do not accept interval alignment."
            )
        selected = [charge[0], discharge[0]]
        reconstructor = CurrentReconstructor("pair")
    selections: list[_Selection] = []
    for match in selected:
        if match.unit is None:
            raise UnknownUnitError(
                "Capacity reconstruction requires a known capacity unit."
            )
        conversion_factor("capacity", match.unit)
        selections.append(_Selection("capacity", match.source_position, match.unit))
    return reconstructor, tuple(selections)


def _reconstructed_records(
    records: Iterator[list[str]],
    time_selection: _Selection,
    capacity_selections: tuple[_Selection, ...],
    decimal: str,
    reconstructor: CurrentReconstructor,
) -> Iterator[list[str]]:
    """Append interval current to source rows with bounded adjacent-row state.

    Convert time/capacity to seconds/mAh, call observe before interval(), and
    retain original adjacency. Previous alignment yields its first NaN; next
    alignment holds one pending row and yields its final NaN. Exhaustion calls
    finish() so an entirely unusable reconstruction cannot report success.
    """
    previous: tuple[float, tuple[float, ...]] | None = None
    pending: list[str] | None = None
    selections = (time_selection, *capacity_selections)
    factors = tuple(conversion_factor(s.key, s.unit) for s in selections)
    for row in records:
        values: list[float] = []
        for selection, factor in zip(selections, factors, strict=True):
            text = row[selection.position].strip()
            normalized = (
                text.replace(",", ".") if decimal == "," and "." not in text else text
            )
            try:
                value = float(normalized) if text else math.nan
                if decimal == "," and "." in text:
                    value = math.nan
            except ValueError:
                value = math.nan
            if text and math.isnan(value) and selection.key != "time":
                warnings.warn(MalformedValueWarning({selection.key: 1}), stacklevel=3)
            values.append(value * factor)
        current_row = (values[0], tuple(values[1:]))
        reconstructor.observe(*current_row)
        if reconstructor.alignment == "next":
            if previous is not None and pending is not None:
                value = repr(reconstructor.interval(previous, current_row))
                yield [*pending, "" if value == "nan" else value.replace(".", decimal)]
            pending = row
        else:
            current = (
                math.nan
                if previous is None
                else reconstructor.interval(previous, current_row)
            )
            yield [
                *row,
                "" if math.isnan(current) else repr(current).replace(".", decimal),
            ]
        previous = current_row
    if pending is not None:
        yield [*pending, ""]
    if previous is None:
        raise IncompatibleDataError("Delimited source contains no scientific rows.")
    if reconstructor.last_finite_time is None:
        raise IncompatibleDataError(
            "Time contains no finite value in the complete source."
        )
    reconstructor.finish()


def _numeric_values(
    rows: Sequence[Sequence[str]],
    selection: _Selection,
    decimal: str,
) -> tuple[NDArray[np.float64], int]:
    """Convert one selected source field without dropping malformed cells.

    Return (float64_values, malformed_nonempty_count). Honor decimal rules,
    parse elapsed clock time only in seconds, and apply the verified unit scale.
    NaN remains in its original position; the caller emits grouped warnings.
    The object Series avoids an unnecessary intermediate Arrow string conversion.
    """
    original = [row[selection.position].strip() for row in rows]
    normalized = [
        (
            value.replace(",", ".")
            if decimal == "," and value and "." not in value
            else ("<invalid-decimal>" if decimal == "," and "." in value else value)
        )
        for value in original
    ]
    if selection.key == "time" and any(":" in value for value in normalized):
        if conversion_factor(selection.key, selection.unit) != 1:
            raise IncompatibleDataError("Clock time requires seconds as its unit.")
        for index, value in enumerate(normalized):
            if ":" not in value:
                continue
            match = re.fullmatch(r"(\d+):([0-5]\d):([0-5]\d(?:\.\d+)?)", value)
            normalized[index] = (
                str(int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3]))
                if match
                else "<invalid-clock>"
            )
    series = pd.Series(normalized, dtype=object)
    numeric = numeric_values(series)
    missing_positions: NDArray[np.intp] = np.isnan(numeric).nonzero()[0]
    malformed = sum(1 for index in missing_positions if original[int(index)] != "")
    factor = conversion_factor(selection.key, selection.unit)
    return (
        numeric if factor == 1.0 else np.multiply(numeric, factor, dtype=np.float64)
    ), malformed


def _standardize_rows(
    rows: Sequence[Sequence[str]],
    selections: tuple[_Selection, _Selection, _Selection],
    decimal: str,
    *,
    time_origin: float | None,
    previous_time: float | None,
    normalize_time: bool,
) -> tuple[pd.DataFrame, float | None, float | None]:
    """Convert one chunk and carry its global time origin and finite endpoint.

    Return (canonical_frame, origin, previous_time). Normalize generic time
    only once, preserve NaN and duplicates, and compare finite values across
    missing rows and chunk boundaries. Canonical text keeps its existing origin.
    Malformed values warn; backward time or infinity raises a domain error.
    """
    arrays: dict[str, NDArray[np.float64]] = {}
    malformed_counts: dict[str, int] = {}
    canonical_names = (TIME_COLUMN, CURRENT_COLUMN, VOLTAGE_COLUMN)
    for selection, canonical in zip(selections, canonical_names, strict=True):
        values, malformed = _numeric_values(rows, selection, decimal)
        arrays[canonical] = values
        if malformed:
            malformed_counts[canonical] = malformed
    if malformed_counts:
        warnings.warn(MalformedValueWarning(malformed_counts), stacklevel=3)

    times = arrays[TIME_COLUMN]
    if np.isinf(times).any():
        raise IncompatibleDataError("Time contains infinite values.")
    finite = times[np.isfinite(times)]
    if finite.size:
        if time_origin is None:
            time_origin = float(finite[0])
        if (previous_time is not None and finite[0] < previous_time) or (
            finite[1:] < finite[:-1]
        ).any():
            from battread.exceptions import NonMonotonicTimeError

            raise NonMonotonicTimeError(
                "Finite time decreases within or across source chunks."
            )
        previous_time = float(finite[-1])
        if normalize_time:
            arrays[TIME_COLUMN] = times - time_origin
    for canonical in (CURRENT_COLUMN, VOLTAGE_COLUMN):
        if np.isinf(arrays[canonical]).any():
            raise IncompatibleDataError(f"{canonical} contains infinite values.")
    frame = pd.DataFrame(arrays, columns=[TIME_COLUMN, CURRENT_COLUMN, VOLTAGE_COLUMN])
    return frame, time_origin, previous_time


class DelimitedReader:
    """Decode generic and canonical CSV/TXT using conservative structural recognition.

    Register an instance with ReaderRegistry. A bounded prefix establishes text
    conventions before row parsing. inspect() explains decisions; read() collects
    output; iter_read() keeps time and capacity state across bounded row buffers.
    Uncertain scientific selectors require explicit user declarations.
    """

    name = "delimited"
    capabilities = ReaderCapabilities(
        streaming=True, text_options=True, formats=("csv", "txt")
    )

    def detect(self, path: Path) -> FormatInfo | None:
        """Recognize supported text structure and report delimiter evidence.

        Read only a bounded prefix. Extension evidence may allow dispatch for an
        explicitly configured dialect; detection does not validate all scientific rows.
        """
        try:
            encoding, text = _decode_prefix(path, None)
        except CorruptedFileError:
            return None
        suffix = path.suffix.casefold()
        lines = text.splitlines()[:_SAMPLE_RECORDS]
        try:
            separator = _detect_separator(lines)
        except IncompatibleDataError:
            if suffix not in {".csv", ".txt"}:
                return None
            return FormatInfo(
                "csv" if suffix == ".csv" else "txt",
                self.name,
                0.55,
                (f"valid {encoding} text", "recognized text-file extension"),
            )
        format_name = "csv" if suffix == ".csv" else "txt"
        confidence = 0.85 if suffix in {".csv", ".txt"} else 0.65
        return FormatInfo(
            format_name,
            self.name,
            confidence,
            (f"valid {encoding} delimited text", f"detected {separator!r} separator"),
        )

    def inspect(self, path: Path, options: ReadOptions) -> InspectionResult:
        """Explain parser structure and selected/rejected columns without reading all
        rows.

        Use the same plan and option precedence as read(). Return unresolved or
        ambiguous candidates instead of requiring a successful conversion.
        """
        plan = _make_plan(path, options)
        matches = _inspection_matches(
            plan, options, prefer_total_time=path.suffix.casefold() == ".csv"
        )
        format_name = "csv" if path.suffix.casefold() == ".csv" else "txt"
        return InspectionResult(
            format=format_name,
            reader=self.name,
            columns=matches,
            delimiter=plan.separator,
            decimal_separator=plan.decimal,
            encoding=plan.encoding,
            current_reconstruction_required=_strategy(matches),
        )

    def read(self, path: Path, options: ReadOptions) -> pd.DataFrame:
        """Collect standardized chunks into one validated complete pandas frame.

        This intentionally uses full-result memory. Emit complete-dataset missing
        counts once; use iter_read for a reader-supported bounded-memory workflow.
        """
        chunks = list(
            self._iter_read(
                path,
                options,
                chunk_size=_DEFAULT_READ_CHUNK,
                emit_missing=False,
            )
        )
        if not chunks:
            raise IncompatibleDataError("Delimited source contains no scientific rows.")
        result = pd.concat(chunks, ignore_index=True)
        validate_standardized(result)
        return result

    def iter_read(
        self, path: Path, options: ReadOptions, *, chunk_size: int
    ) -> Iterator[pd.DataFrame]:
        """Return the canonical chunk iterator with per-chunk missing-value warnings.

        Use an existing path, validated options and positive chunk_size. Consume
        the iterator fully to complete global finite-time and reconstruction checks.
        """
        return self._iter_read(path, options, chunk_size=chunk_size, emit_missing=True)

    def _iter_read(
        self,
        path: Path,
        options: ReadOptions,
        *,
        chunk_size: int,
        emit_missing: bool,
    ) -> Iterator[pd.DataFrame]:
        """Plan generic text and connect its record stream to the shared table pipeline.

        Vendor adapters override this boundary, allowing them to reuse the same
        scientific conversion without depending on generic text decoding.
        """
        plan = _make_plan(path, options)
        matches = _inspection_matches(
            plan, options, prefer_total_time=path.suffix.casefold() == ".csv"
        )
        return self._iter_table(
            plan,
            options,
            matches,
            _iter_source_records(path, plan, options.skiprows),
            chunk_size=chunk_size,
            emit_missing=emit_missing,
        )

    def _iter_table(
        self,
        plan: _TablePlan,
        options: ReadOptions,
        matches: tuple[ColumnMatch, ...],
        records: Iterator[list[str]],
        *,
        chunk_size: int,
        emit_missing: bool,
        source_matches: tuple[ColumnMatch, ...] | None = None,
    ) -> Iterator[pd.DataFrame]:
        """Standardize a logical source with direct-current priority and shared state.

        Accept a structural plan, interpreted matches and full-width string rows.
        Only enter reconstruction when measured-current selection is unavailable;
        missing measured samples never justify replacement. Carry origin, finite
        time and lookahead across chunks, warn as requested, and validate at exhaustion.
        source_matches preserves original reset evidence when overrides change
        semantics.
        """
        time_selection = _selection_for("time", plan, options, matches)
        voltage_selection = _selection_for("voltage", plan, options, matches)
        capacity_selections: tuple[_Selection, ...] = ()
        try:
            current_selection = _selection_for("current", plan, options, matches)
        except MissingColumnError as error:
            if any(
                match.quantity == "capacity" and match.state == "ambiguous"
                for match in matches
            ):
                raise AmbiguousColumnError(
                    "Capacity candidates are ambiguous; provide explicit mappings."
                ) from error
            capacity_found = any(
                match.quantity == "capacity" and match.state in {"resolved", "explicit"}
                for match in matches
            )
            if capacity_found:
                reconstructor, capacity_selections = _capacity_strategy(
                    matches, options
                )
                original_matches = source_matches or recognize_columns(plan.columns)
                reconstructor.monotonic_indices = tuple(
                    index
                    for index, selection in enumerate(capacity_selections)
                    if original_matches[selection.position].semantic
                    in {"charge_capacity", "discharge_capacity"}
                )
                current_selection = _Selection("current", plan.width, "mA")
            else:
                raise error
        else:
            reconstructor = None
        selections = (time_selection, current_selection, voltage_selection)

        rows: list[list[str]] = []
        time_origin: float | None = None
        previous_time: float | None = None
        yielded = False
        if reconstructor is not None:
            records = _reconstructed_records(
                records,
                time_selection,
                capacity_selections,
                plan.decimal,
                reconstructor,
            )
        for row in records:
            rows.append(row)
            if len(rows) < chunk_size:
                continue
            frame, time_origin, previous_time = _standardize_rows(
                rows,
                selections,
                plan.decimal,
                time_origin=time_origin,
                previous_time=previous_time,
                normalize_time=not plan.canonical,
            )
            if emit_missing:
                self._warn_missing(frame)
            yielded = True
            yield frame
            rows = []
        if rows:
            frame, time_origin, previous_time = _standardize_rows(
                rows,
                selections,
                plan.decimal,
                time_origin=time_origin,
                previous_time=previous_time,
                normalize_time=not plan.canonical,
            )
            if emit_missing:
                self._warn_missing(frame)
            yielded = True
            yield frame
        if not yielded:
            raise IncompatibleDataError("Delimited source contains no scientific rows.")
        if time_origin is None:
            raise IncompatibleDataError(
                "Time contains no finite value in the complete source."
            )
        if plan.canonical and time_origin != 0.0:
            raise IncompatibleDataError(
                "The first finite canonical time must be 0 seconds; "
                f"received {time_origin!r}."
            )

    @staticmethod
    def _warn_missing(frame: pd.DataFrame) -> None:
        """Emit per-column NaN counts for one retained canonical chunk.

        Counts sum across chunks independently of chunk size; warning emission
        must never alter source values or remove a row.
        """
        counts = {
            column: count
            for column in frame.columns
            if (count := int(frame[column].isna().sum()))
        }
        if counts:
            warnings.warn(MissingValueWarning(counts), stacklevel=3)
