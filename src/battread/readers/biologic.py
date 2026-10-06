# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bio-Logic adapters with an isolated, optional Galvani binary backend."""

# Shared internal table machinery is intentionally reused by vendor adapters.
# pyright: reportPrivateUsage=false

import csv
import math
import re
from collections.abc import Generator, Iterator
from dataclasses import replace
from importlib import import_module
from pathlib import Path
from typing import cast

import pandas as pd

from battread.exceptions import (
    CorruptedFileError,
    IncompatibleDataError,
    MissingDependencyError,
)
from battread.readers.delimited import (
    DelimitedReader,
    _decode_prefix,
    _detect_decimal,
    _inspection_matches,
    _strategy,
    _TablePlan,
)
from battread.readers.models import FormatInfo, ReaderCapabilities, ReadOptions
from battread.readers.mpr import MPR_MAGIC, GalvaniSchema, MPRLayout, inspect_layout
from battread.recognition import recognize_columns
from battread.recognition.models import ColumnMatch, InspectionResult, ReaderHint

_MPR_MAGIC = MPR_MAGIC
_MPT_MAGIC = (b"EC-Lab ASCII FILE", b"BT-Lab ASCII FILE")


def _load_mpr(path: Path) -> MPRLayout:
    """Resolve the optional schema backend and inspect bounded binary metadata.

    No complete acquisition is allocated. MissingDependencyError still identifies
    the biologic extra; scientific interpretation remains in the shared pipeline.
    """
    try:
        backend = cast(GalvaniSchema, import_module("galvani.BioLogic"))
    except ImportError as error:
        raise MissingDependencyError(
            'Bio-Logic MPR support requires pip install "battread[biologic]".'
        ) from error
    return inspect_layout(path, backend)


def _hints(columns: tuple[str | int, ...]) -> tuple[ReaderHint, ...]:
    """Declare measured fields and verified Bio-Logic capacity semantics."""
    declared: dict[str, ReaderHint] = {
        "time/s": ReaderHint("time/s", "time", "s"),
        "I/mA": ReaderHint("I/mA", "current", "mA"),
        "<I>/mA": ReaderHint("<I>/mA", "current", "mA"),
        "Ewe/V": ReaderHint("Ewe/V", "voltage", "V"),
        "<Ewe>/V": ReaderHint("<Ewe>/V", "voltage", "V"),
        "<Ewe/V>": ReaderHint("<Ewe/V>", "voltage", "V"),
        "Ecell/V": ReaderHint("Ecell/V", "voltage", "V"),
        "Q charge/mA.h": ReaderHint(
            "Q charge/mA.h", "capacity", "mAh", "charge_capacity"
        ),
        "Q discharge/mA.h": ReaderHint(
            "Q discharge/mA.h", "capacity", "mAh", "discharge_capacity"
        ),
        # Verified EC-Lab/BT-Lab interval charge, ending at the recorded row.
        "dq/mA.h": ReaderHint("dq/mA.h", "capacity", "mAh", "delta_signed", "previous"),
        "dQ/mA.h": ReaderHint("dQ/mA.h", "capacity", "mAh", "delta_signed", "previous"),
        "dQ/C": ReaderHint("dQ/C", "capacity", "C", "delta_signed", "previous"),
        "(Q-Qo)/mA.h": ReaderHint("(Q-Qo)/mA.h", "capacity", "mAh", "unknown_capacity"),
        "(Q-Qo)/C": ReaderHint("(Q-Qo)/C", "capacity", "C", "unknown_capacity"),
    }
    result: list[ReaderHint] = []
    for index, column in enumerate(columns):
        if not isinstance(column, str):
            continue
        # Galvani appends ordinal suffixes to duplicate binary column names.
        base = re.sub(r" \d+$", "", column)
        if base in declared:
            result.append(
                replace(declared[base], source_column=column, source_position=index)
            )
    return tuple(result)


def _binary_options(options: ReadOptions) -> None:
    """Reject text-parser settings that have no scientific meaning for binary MPR.

    Explicit column/unit/semantic options are handled later; sep, encoding,
    header and skiprows cannot silently alter a binary layout.
    """
    if (
        options.sep is not None
        or options.decimal is not None
        or options.encoding is not None
        or options.header != "infer"
        or options.skiprows != 0
    ):
        raise IncompatibleDataError("Text parsing options are unsupported for MPR.")


def _matches(plan: _TablePlan, options: ReadOptions) -> tuple[ColumnMatch, ...]:
    """Combine Bio-Logic hints with user overrides while excluding AC magnitudes.

    Known signed dq retains previous alignment unless explicitly overridden.
    Magnitude fields are not signed cycling measurements; only explicit
    selection can bypass that automatic exclusion.
    """
    matches = _inspection_matches(
        plan, options, vendor="biologic", hints=_hints(plan.columns)
    )
    # Preserve authoritative interval semantics when only a selector is supplied.
    hints = {hint.source_position: hint for hint in _hints(plan.columns)}
    matches = tuple(
        replace(
            match,
            semantic="delta_signed",
            interval_alignment=options.capacity_interval or "previous",
            evidence=(
                *match.evidence,
                "verified Bio-Logic signed dq; "
                f"{options.capacity_interval or 'previous'} alignment",
            ),
        )
        if match.quantity == "capacity"
        and match.state in {"resolved", "explicit", "ambiguous"}
        and match.source_position in hints
        and hints[match.source_position].semantic == "delta_signed"
        and options.capacity_kind in {None, "delta_signed"}
        else match
        for match in matches
    )
    return tuple(
        replace(
            match,
            state="unresolved",
            confidence=0.0,
            evidence=(
                *match.evidence,
                "AC magnitude is not a signed cycling measurement",
            ),
        )
        if isinstance(match.source_column, str)
        and match.source_column.startswith(("|I|/", "|Ewe|/"))
        and match.state != "explicit"
        else match
        for match in matches
    )


class BioLogicMPRReader(DelimitedReader):
    """Decode Bio-Logic binary data through the isolated optional Galvani adapter.

    Register an instance with ReaderRegistry. read() collects canonical output;
    iter_read() reads bounded binary batches; Galvani supplies metadata/schema
    definitions without loading the full acquisition. Measured current takes
    precedence; established
    signed dq is a fallback only when direct current is absent.
    """

    name = "biologic-mpr"
    capabilities = ReaderCapabilities(True, False, ("mpr",))

    def detect(self, path: Path) -> FormatInfo | None:
        """Recognize MPR magic, with an extension fallback for actionable parse errors.

        Detection reads a prefix only; it does not claim the full backend schema
        is supported or validate the complete acquisition.
        """
        with path.open("rb") as stream:
            magic = stream.read(len(_MPR_MAGIC))
        if magic == _MPR_MAGIC:
            return FormatInfo("mpr", self.name, 1.0, ("Bio-Logic binary magic",))
        if path.suffix.casefold() == ".mpr":
            return FormatInfo(
                "mpr", self.name, 0.95, ("MPR extension; header requires validation",)
            )
        return None

    @staticmethod
    def _table(path: Path, options: ReadOptions) -> tuple[_TablePlan, MPRLayout]:
        """Inspect binary metadata and construct a positional shared table plan.

        Return the plan and bounded source descriptor. Keep duplicate field names
        separate and expose only the adapter's internal representation.
        """
        _binary_options(options)
        data = _load_mpr(path)
        columns = cast(tuple[str | int, ...], data.dtype.names)
        return _TablePlan("", "", ".", None, columns, len(columns), False), data

    def inspect(self, path: Path, options: ReadOptions) -> InspectionResult:
        """Explain binary fields after bounded metadata and option validation.

        Measurement values are not read; malformed container framing still fails.
        Return candidates even when later scientific selection is ambiguous.
        """
        plan, _ = self._table(path, options)
        matches = _matches(plan, options)
        return InspectionResult(
            "mpr",
            self.name,
            matches,
            current_reconstruction_required=_strategy(matches),
        )

    def _iter_read(
        self,
        path: Path,
        options: ReadOptions,
        *,
        chunk_size: int,
        emit_missing: bool,
    ) -> Iterator[pd.DataFrame]:
        """Connect bounded binary batches to the unchanged scientific pipeline.

        Yield at most the requested rows. Wide schemas reduce the effective chunk
        size to bound the full-width string-row buffers used by shared conversion.
        """
        plan, layout = self._table(path, options)
        matches = _matches(plan, options)
        # 128 bytes per source cell is a conservative buffer-sizing heuristic,
        # not a promise of total process RAM or a scientific conversion factor.
        effective = min(chunk_size, max(1, 8 * 1024**2 // (128 * plan.width)))
        return self._canonical_chunks(
            plan, options, matches, layout, effective, emit_missing
        )

    def _canonical_chunks(
        self,
        plan: _TablePlan,
        options: ReadOptions,
        matches: tuple[ColumnMatch, ...],
        layout: MPRLayout,
        chunk_size: int,
        emit_missing: bool,
    ) -> Generator[pd.DataFrame, None, None]:
        """Own source-record lifetime, closing file resources on any iterator exit."""
        records = self._records(layout, chunk_size)
        try:
            yield from self._iter_table(
                plan,
                options,
                matches,
                records,
                chunk_size=chunk_size,
                emit_missing=emit_missing,
                source_matches=recognize_columns(
                    plan.columns, vendor="biologic", hints=_hints(plan.columns)
                ),
            )
        finally:
            records.close()

    @staticmethod
    def _records(
        layout: MPRLayout, chunk_size: int
    ) -> Generator[list[str], None, None]:
        """Yield original-width source rows while retaining only one binary batch.

        Numeric string representations match the former Galvani-array path;
        nonfinite/malformed fields still enter the existing shared validation.
        """
        names = layout.dtype.names
        assert names is not None
        batches = layout.iter_arrays(chunk_size)
        try:
            for batch in batches:
                for record in batch:
                    try:
                        values = [float(record[name]) for name in names]
                    except (TypeError, ValueError) as error:
                        raise CorruptedFileError(
                            "MPR backend returned nonnumeric source fields."
                        ) from error
                    yield ["" if math.isnan(value) else repr(value) for value in values]
                    del record
                del batch
        finally:
            close = getattr(batches, "close", None)
            if close is not None:
                close()


def _mpt_plan(path: Path, options: ReadOptions) -> tuple[_TablePlan, int]:
    """Validate EC-Lab/BT-Lab ASCII framing and declared header length.

    Return a shared plan and physical table offset using supported encoding
    and decimal options. The declared header identifies columns; malformed
    framing or unsupported overrides must fail rather than guess an offset.
    """
    if (
        options.sep not in {None, "\t"}
        or options.header not in {"infer", 0}
        or options.skiprows
    ):
        raise IncompatibleDataError(
            "MPT has a declared tab-separated header; "
            "sep/header/skiprows cannot replace it."
        )
    encoding, _ = _decode_prefix(path, options.encoding)
    try:
        with path.open("r", encoding=encoding, errors="strict", newline="") as stream:
            magic = stream.readline().strip().encode("ascii")
            if magic not in _MPT_MAGIC:
                raise ValueError("Missing EC-Lab/BT-Lab ASCII magic")
            match = re.fullmatch(r"Nb header lines\s*:\s*(\d+)\s*", stream.readline())
            if match is None or int(match[1]) < 3:
                raise ValueError("Invalid declared MPT header length")
            count = int(match[1])
            line = ""
            for _ in range(count - 2):
                line = stream.readline()
                if not line:
                    raise ValueError("Truncated MPT header")
            columns = tuple(cell.strip() for cell in line.rstrip("\r\n\t").split("\t"))
            if len(columns) < 2 or any(not column for column in columns):
                raise ValueError("Invalid MPT column header")
            sample = list(
                csv.reader([stream.readline() for _ in range(80)], delimiter="\t")
            )
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        raise CorruptedFileError(f"Invalid Bio-Logic MPT header: {error}.") from error
    decimal = options.decimal or _detect_decimal(sample, None)
    return _TablePlan(
        encoding, "\t", decimal, None, columns, len(columns), False
    ), count


class BioLogicMPTReader(DelimitedReader):
    """Stream declared Bio-Logic EC-Lab/BT-Lab text tables without Galvani.

    Register an instance with ReaderRegistry. Header validation establishes
    the table start and vendor column hints before shared delimited processing.
    read() collects output; iter_read() maintains time and reconstruction state
    while consuming text records incrementally.
    """

    name = "biologic-mpt"
    capabilities = ReaderCapabilities(True, True, ("mpt",))

    def detect(self, path: Path) -> FormatInfo | None:
        """Recognize ASCII instrument magic or decline an unrelated source.

        Detection examines the prefix; the declared header and rows are checked
        when inspection or ingestion builds the MPT plan.
        """
        with path.open("rb") as stream:
            magic = stream.readline(64).strip()
        if magic in _MPT_MAGIC:
            return FormatInfo("mpt", self.name, 1.0, ("EC-Lab/BT-Lab ASCII magic",))
        if path.suffix.casefold() == ".mpt":
            return FormatInfo(
                "mpt", self.name, 0.95, ("MPT extension; header requires validation",)
            )
        return None

    def inspect(self, path: Path, options: ReadOptions) -> InspectionResult:
        """Read declared ASCII metadata and explain Bio-Logic column interpretation.

        Return matches with verified hints and explicit overrides, without
        requiring the complete table to be loaded or scientifically convertible.
        """
        plan, _ = _mpt_plan(path, options)
        matches = _matches(plan, options)
        return InspectionResult(
            "mpt",
            self.name,
            matches,
            plan.separator,
            plan.decimal,
            plan.encoding,
            _strategy(matches),
        )

    def _iter_read(
        self,
        path: Path,
        options: ReadOptions,
        *,
        chunk_size: int,
        emit_missing: bool,
    ) -> Iterator[pd.DataFrame]:
        """Connect native MPT text streaming to canonical conversion and reconstruction.

        Use the declared header offset, retain original record order and share
        the same Bio-Logic semantics as MPR without requiring Galvani.
        """
        plan, count = _mpt_plan(path, options)
        hints = _hints(plan.columns)
        matches = _matches(plan, options)
        return self._iter_table(
            plan,
            options,
            matches,
            self._records(path, plan, count),
            chunk_size=chunk_size,
            emit_missing=emit_missing,
            source_matches=recognize_columns(
                plan.columns, vendor="biologic", hints=hints
            ),
        )

    @staticmethod
    def _records(path: Path, plan: _TablePlan, count: int) -> Iterator[list[str]]:
        """Stream tab-separated measurements after the declared physical header.

        Validate every row width and strict decoding. Empty values remain cells;
        structural corruption fails rather than silently skipping measurements.
        """
        try:
            with path.open(
                "r", encoding=plan.encoding, errors="strict", newline=""
            ) as stream:
                for _ in range(count):
                    stream.readline()
                for index, row in enumerate(
                    csv.reader(stream, delimiter="\t", strict=True), count + 1
                ):
                    if not row:
                        continue
                    if len(row) == plan.width + 1 and not row[-1].strip():
                        # EC-Lab's optional terminal tab is structural padding.
                        row.pop()
                    if len(row) != plan.width:
                        raise CorruptedFileError(
                            f"MPT record at line {index} has {len(row)} fields; "
                            f"expected {plan.width}."
                        )
                    yield row
        except (OSError, UnicodeError, csv.Error) as error:
            raise CorruptedFileError(
                f"Malformed MPT scientific table: {error}."
            ) from error
