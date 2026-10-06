# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Public source-reading API backed by the reader registry."""

from collections.abc import Iterator, Mapping
from os import PathLike
from pathlib import Path
from types import MappingProxyType
from typing import cast

import pandas as pd

from battread.exceptions import IncompatibleDataError
from battread.readers.biologic import BioLogicMPRReader, BioLogicMPTReader
from battread.readers.delimited import DelimitedReader
from battread.readers.models import (
    CapacityKind,
    ColumnMapping,
    FormatInfo,
    HeaderOption,
    ReadOptions,
    SemanticKey,
    SourceSelector,
    UnitMapping,
)
from battread.readers.neware import NewareReader
from battread.readers.parquet import CanonicalParquetReader
from battread.readers.registry import ReaderRegistry
from battread.recognition.models import InspectionResult, IntervalAlignment

_SEMANTIC_KEYS = frozenset(
    {
        "time",
        "current",
        "voltage",
        "capacity",
        "charge_capacity",
        "discharge_capacity",
    }
)
_REGISTRY = ReaderRegistry()
# Specialized adapters register before the generic text fallback so equally
# strong detection evidence keeps the more specific container interpretation.
_REGISTRY.register(NewareReader())
_REGISTRY.register(BioLogicMPRReader())
_REGISTRY.register(BioLogicMPTReader())
_REGISTRY.register(CanonicalParquetReader())
_REGISTRY.register(DelimitedReader())


def _path(source: str | PathLike[str]) -> Path:
    """Validate a source path before any reader opens it.

    Accept a string or PathLike and return a Path for an existing file. Raise
    IncompatibleDataError for missing files or directories, so callers receive
    a package error instead of an incidental low-level file-open failure.
    """
    path = Path(source)
    if not path.is_file():
        raise IncompatibleDataError(f"Source file does not exist: {path}.")
    return path


def _column_mapping(
    columns: Mapping[str, str | int] | None,
) -> ColumnMapping:
    """Freeze explicit semantic-to-source selectors for all reader adapters.

    Accept None or a mapping from supported semantic keys to column names or
    zero-based positions. Reject unsupported keys, empty names and booleans
    masquerading as integer positions. Return an immutable copy so caller
    mutation cannot change a conversion already in progress.
    """
    if columns is None:
        return MappingProxyType({})
    result: dict[SemanticKey, SourceSelector] = {}
    for raw_key, selector in columns.items():
        if raw_key not in _SEMANTIC_KEYS:
            raise IncompatibleDataError(f"Unsupported semantic column key {raw_key!r}.")
        if type(selector) not in {str, int}:
            raise IncompatibleDataError(
                f"Column selector for {raw_key!r} must be a name or "
                "zero-based position."
            )
        if isinstance(selector, str) and not selector:
            raise IncompatibleDataError(f"Column name for {raw_key!r} cannot be empty.")
        result[cast(SemanticKey, raw_key)] = selector
    return MappingProxyType(result)


def _unit_mapping(units: Mapping[str, str] | None) -> UnitMapping:
    """Validate and freeze user unit overrides before dispatch.

    Accept None or semantic keys mapped to nonempty unit strings. This checks
    option structure; quantity compatibility is checked when the selected
    reader resolves each field. Return an immutable mapping.
    """
    if units is None:
        return MappingProxyType({})
    result: dict[SemanticKey, str] = {}
    for raw_key, unit in units.items():
        if raw_key not in _SEMANTIC_KEYS:
            raise IncompatibleDataError(f"Unsupported semantic unit key {raw_key!r}.")
        if type(unit) is not str or not unit.strip():
            raise IncompatibleDataError(
                f"Unit for {raw_key!r} must be a nonempty string."
            )
        result[cast(SemanticKey, raw_key)] = unit
    return MappingProxyType(result)


def _options(
    *,
    columns: Mapping[str, str | int] | None,
    units: Mapping[str, str] | None,
    capacity_kind: str | None,
    capacity_interval: str | None,
    autodetect: bool,
    sep: str | None,
    decimal: str | None,
    encoding: str | None,
    header: HeaderOption,
    skiprows: int,
) -> ReadOptions:
    """Build the shared reader configuration at the public API boundary.

    Validate column/unit mappings, capacity declarations and text-parser
    settings before constructing ReadOptions. In particular, capacity_kind
    requires an explicit capacity selector; declaring semantics must never
    silently choose a different source field. Raise IncompatibleDataError
    for invalid option shapes. Reader-specific restrictions are checked later.
    """
    column_mapping = _column_mapping(columns)
    unit_mapping = _unit_mapping(units)
    if capacity_kind not in {None, "cumulative_signed", "delta_signed"}:
        raise IncompatibleDataError(
            "capacity_kind must be None, 'cumulative_signed', or 'delta_signed'."
        )
    if capacity_kind is not None and "capacity" not in column_mapping:
        raise IncompatibleDataError(
            "A non-None capacity_kind requires an explicit columns['capacity'] mapping."
        )
    if capacity_interval not in {None, "previous", "next"}:
        raise IncompatibleDataError(
            "capacity_interval must be None, 'previous', or 'next'."
        )
    if type(autodetect) is not bool:
        raise IncompatibleDataError("autodetect must be a boolean.")
    if sep is not None and not (
        sep == "whitespace" or (len(sep) == 1 and sep not in {"\r", "\n", '"'})
    ):
        raise IncompatibleDataError(
            "sep must be one character or the literal 'whitespace'; regular "
            "expressions are unsupported."
        )
    if decimal not in {None, ".", ","}:
        raise IncompatibleDataError("decimal must be None, '.', or ','.")
    if encoding is not None and (type(encoding) is not str or not encoding):
        raise IncompatibleDataError("encoding must be a nonempty codec name or None.")
    if not (header in {None, "infer"} or (type(header) is int and header >= 0)):
        raise IncompatibleDataError(
            "header must be 'infer', None, or a non-negative integer."
        )
    if type(skiprows) is not int or skiprows < 0:
        raise IncompatibleDataError("skiprows must be a non-negative integer.")
    return ReadOptions(
        columns=column_mapping,
        units=unit_mapping,
        capacity_kind=cast(CapacityKind | None, capacity_kind),
        capacity_interval=cast(IntervalAlignment | None, capacity_interval),
        autodetect=autodetect,
        sep=sep,
        decimal=decimal,
        encoding=encoding,
        header=header,
        skiprows=skiprows,
    )


def _reader_name(reader: str | None) -> str | None:
    """Translate public format aliases into registered adapter names.

    For example, csv and txt both select delimited, while nda and ndax select
    neware. Unknown names pass through for the registry's actionable error.
    This resolves names only; the registry still validates source detection.
    """
    if reader in {"nda", "ndax"}:
        return "neware"
    if reader in {"mpr", "mpt"}:
        return f"biologic-{reader}"
    if reader in {"csv", "txt", "generic"}:
        return "delimited"
    if reader in {"parquet", "canonical-parquet"}:
        return "parquet"
    return reader


def detect_format(path: str | PathLike[str]) -> FormatInfo:
    """Detect a source adapter without standardizing scientific rows.

    This is a structural routing aid, not proof of valid data or safe column meaning.
    Vendor dependencies remain optional until their adapter needs to decode data.

    Args:
        path: Existing source path, supplied as a string or PathLike.

    Returns:
        FormatInfo containing format, reader, confidence and detection evidence.

    Raises:
        IncompatibleDataError: The path does not name an existing file.
        UnsupportedFormatError: No registered adapter recognizes the source.

    Examples:
        >>> info = detect_format("experiment.csv")  # doctest: +SKIP
        >>> info.reader  # doctest: +SKIP
        'delimited'
    """
    source = _path(path)
    _, information = _REGISTRY.select(source)
    return information


def inspect(
    path: str | PathLike[str],
    *,
    reader: str | None = None,
    columns: Mapping[str, str | int] | None = None,
    units: Mapping[str, str] | None = None,
    capacity_kind: CapacityKind | None = None,
    capacity_interval: IntervalAlignment | None = None,
    autodetect: bool = True,
    sep: str | None = None,
    decimal: str | None = None,
    encoding: str | None = None,
    header: HeaderOption = "infer",
    skiprows: int = 0,
) -> InspectionResult:
    """Explain source structure and column decisions before attempting conversion.

    Use the same options as read(). Ambiguous/unresolved matches stay visible
    with evidence rather than forcing successful conversion. Generic text
    inspection samples bounded records; MPR scans bounded metadata and split
    NDAX scans metadata/primary blocks. Inspection is not whole-source validation.

    Args:
        path: Existing source file; content-based registry detection takes precedence
            over an arbitrary filename extension.
        reader: Optional registered adapter or format alias, such as csv or mpr.
        columns: Semantic keys mapped to source names or zero-based positions.
            Duplicate names require positions; explicit mappings override recognition.
        units: Unit overrides keyed by quantity; compatibility is still validated.
        capacity_kind: cumulative_signed or delta_signed for an explicitly selected
            capacity field; ignored as a reconstruction trigger when direct current
            exists.
        capacity_interval: previous or next incremental alignment. Cumulative
            reconstruction does not accept an alignment declaration.
        autodetect: Enable semantic recognition; False requires explicit scientific
            choices but still permits unspecified text structure to be detected.
        sep: Literal one-character delimiter, whitespace, or None for detection.
        decimal: Point/comma marker, or None for detection; output units stay canonical.
        encoding: Strict source codec, or None for supported encoding detection.
        header: infer, None for headerless, or a zero-based nonblank table record.
        skiprows: Physical prefix lines to skip before header counting, including
            blanks.

    Returns:
        InspectionResult with positional matches, parser metadata and the known
        reconstruction requirement; unknown decisions remain explicit.

    Raises:
        IncompatibleDataError: Invalid parser/options or unsupported overrides.
        UnsupportedFormatError: No compatible adapter/profile can be selected.
        MissingDependencyError: Binary inspection needs an uninstalled extra.
        CorruptedFileError: Framing or sampled structure cannot be decoded safely.

    Examples:
        >>> result = inspect('experiment.csv')  # doctest: +SKIP
        >>> [(m.source_column, m.state) for m in result.columns]  # doctest: +SKIP
    """
    source = _path(path)
    selected, _ = _REGISTRY.select(source, _reader_name(reader))
    options = _options(
        columns=columns,
        units=units,
        capacity_kind=capacity_kind,
        capacity_interval=capacity_interval,
        autodetect=autodetect,
        sep=sep,
        decimal=decimal,
        encoding=encoding,
        header=header,
        skiprows=skiprows,
    )
    return selected.inspect(source, options)


def read(
    path: str | PathLike[str],
    *,
    reader: str | None = None,
    columns: Mapping[str, str | int] | None = None,
    units: Mapping[str, str] | None = None,
    capacity_kind: CapacityKind | None = None,
    capacity_interval: IntervalAlignment | None = None,
    autodetect: bool = True,
    sep: str | None = None,
    decimal: str | None = None,
    encoding: str | None = None,
    header: HeaderOption = "infer",
    skiprows: int = 0,
) -> pd.DataFrame:
    """Read and validate one complete source as a canonical pandas DataFrame.

    Use this when the full result fits memory. The returned columns are exactly
    time_s, current_mA and voltage_V in float64. Generic/vendor time begins at
    the first finite sample; canonical input must already have a zero origin.
    Direct current, including missing samples, takes precedence over capacity.

    Args:
        path: Existing source file; content-based registry detection takes precedence
            over an arbitrary filename extension.
        reader: Optional registered adapter or format alias, such as csv or mpr.
        columns: Semantic keys mapped to source names or zero-based positions.
            Duplicate names require positions; explicit mappings override recognition.
        units: Unit overrides keyed by quantity; compatibility is still validated.
        capacity_kind: cumulative_signed or delta_signed for an explicitly selected
            capacity field; ignored as a reconstruction trigger when direct current
            exists.
        capacity_interval: previous or next incremental alignment. Cumulative
            reconstruction does not accept an alignment declaration.
        autodetect: Enable semantic recognition; False requires explicit scientific
            choices but still permits unspecified text structure to be detected.
        sep: Literal one-character delimiter, whitespace, or None for detection.
        decimal: Point/comma marker, or None for detection; output units stay canonical.
        encoding: Strict source codec, or None for supported encoding detection.
        header: infer, None for headerless, or a zero-based nonblank table record.
        skiprows: Physical prefix lines to skip before header counting, including
            blanks.

    Returns:
        A complete canonical DataFrame preserving original row order and NaN cells.

    Raises:
        IncompatibleDataError: Invalid options or canonical contract violations.
        AmbiguousColumnError: More than one scientifically plausible field remains.
        MissingColumnError: A required measured quantity cannot be selected.
        UnknownUnitError: A selected field has no supported known unit.
        InvalidUnitError: A known unit is incompatible with its selected quantity.
        CurrentReconstructionError: Capacity semantics or intervals are unsafe.
        NonMonotonicTimeError: Finite source time decreases.
        MissingDependencyError: The requested optional backend is unavailable.
        CorruptedFileError: Source structure or decoding is unsafe.
        UnsupportedFormatError: Source framing or adapter is unsupported.

    Warns:
        MissingValueWarning: Missing canonical values are retained.
        MalformedValueWarning: Nonempty numeric cells were retained as NaN.

    Examples:
        >>> data = read('experiment.csv')  # doctest: +SKIP
        >>> data = read('export.csv', columns={'time': 'Total Time'},
        ...             units={'time': 's'})  # doctest: +SKIP
    """
    source = _path(path)
    selected, _ = _REGISTRY.select(source, _reader_name(reader))
    options = _options(
        columns=columns,
        units=units,
        capacity_kind=capacity_kind,
        capacity_interval=capacity_interval,
        autodetect=autodetect,
        sep=sep,
        decimal=decimal,
        encoding=encoding,
        header=header,
        skiprows=skiprows,
    )
    return selected.read(source, options)


def iter_read(
    path: str | PathLike[str],
    *,
    chunk_size: int = 250_000,
    reader: str | None = None,
    columns: Mapping[str, str | int] | None = None,
    units: Mapping[str, str] | None = None,
    capacity_kind: CapacityKind | None = None,
    capacity_interval: IntervalAlignment | None = None,
    autodetect: bool = True,
    sep: str | None = None,
    decimal: str | None = None,
    encoding: str | None = None,
    header: HeaderOption = "infer",
    skiprows: int = 0,
) -> Iterator[pd.DataFrame]:
    """Yield canonical chunks while preserving one logical source's scientific state.

    Each chunk has the canonical float64 columns. Time is globally normalized,
    not restarted per chunk. Missing-row warnings can be emitted per chunk.
    Consume the iterator fully: whole-source checks may fail after earlier
    chunks were yielded. Use convert() for safe atomic file publication.

    Args:
        path: Existing source file; content-based registry detection takes precedence
            over an arbitrary filename extension.
        chunk_size: Positive maximum row count per canonical chunk. Some adapters,
            may retain format-specific metadata in addition to chunk buffers.
        reader: Optional registered adapter or format alias, such as csv or mpr.
        columns: Semantic keys mapped to source names or zero-based positions.
            Duplicate names require positions; explicit mappings override recognition.
        units: Unit overrides keyed by quantity; compatibility is still validated.
        capacity_kind: cumulative_signed or delta_signed for an explicitly selected
            capacity field; ignored as a reconstruction trigger when direct current
            exists.
        capacity_interval: previous or next incremental alignment. Cumulative
            reconstruction does not accept an alignment declaration.
        autodetect: Enable semantic recognition; False requires explicit scientific
            choices but still permits unspecified text structure to be detected.
        sep: Literal one-character delimiter, whitespace, or None for detection.
        decimal: Point/comma marker, or None for detection; output units stay canonical.
        encoding: Strict source codec, or None for supported encoding detection.
        header: infer, None for headerless, or a zero-based nonblank table record.
        skiprows: Physical prefix lines to skip before header counting, including
            blanks.

    Yields:
        Canonical pandas DataFrames in original source order.

    Raises:
        IncompatibleDataError: Invalid chunk size, options or global data contract.
        DataStandardizationError: The same interpretation/parse errors as read(),
            either at preparation time or during iterator consumption.

    Examples:
        >>> for chunk in iter_read('large.csv', chunk_size=10_000):  # doctest: +SKIP
        ...     process(chunk)

    Notes:
        Chunk size is a row limit, not a strict RAM limit. Backend tables,
        checkpoint dictionaries and Arrow decode buffers may add memory costs.
    """
    if type(chunk_size) is not int or chunk_size <= 0:
        raise IncompatibleDataError("chunk_size must be a positive integer.")
    source = _path(path)
    selected, _ = _REGISTRY.select(source, _reader_name(reader))
    options = _options(
        columns=columns,
        units=units,
        capacity_kind=capacity_kind,
        capacity_interval=capacity_interval,
        autodetect=autodetect,
        sep=sep,
        decimal=decimal,
        encoding=encoding,
        header=header,
        skiprows=skiprows,
    )
    return selected.iter_read(source, options, chunk_size=chunk_size)
