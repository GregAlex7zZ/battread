# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Atomic canonical writers and streaming file conversion."""

# PyArrow does not publish complete type information for its Python boundary.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import os
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, suppress
from os import PathLike
from pathlib import Path
from typing import IO, Literal, TypeAlias

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from battread.api import iter_read
from battread.canonical import coerce_canonical
from battread.exceptions import (
    CorruptedFileError,
    IncompatibleDataError,
    OutputExistsError,
    UnsupportedFormatError,
)
from battread.readers.models import CapacityKind, HeaderOption
from battread.recognition.models import IntervalAlignment

OutputFormat: TypeAlias = Literal["parquet", "csv", "txt"]


def _output_format(destination: Path, requested: OutputFormat | None) -> OutputFormat:
    """Resolve a canonical output format without guessing the data layout.

    Use the explicit parquet/csv/txt request when supplied; otherwise inspect
    the destination suffix. Raise UnsupportedFormatError for unknown formats
    or suffixes. Writers use this before creating any temporary output.
    """
    if requested is not None:
        if requested not in {"parquet", "csv", "txt"}:
            raise UnsupportedFormatError(
                f"Unsupported output format {requested!r}; use parquet, csv, or txt."
            )
        return requested
    suffixes: dict[str, OutputFormat] = {
        ".parquet": "parquet",
        ".csv": "csv",
        ".txt": "txt",
    }
    inferred = suffixes.get(destination.suffix.casefold())
    if inferred is None:
        raise UnsupportedFormatError(
            "Cannot infer output format; use a .parquet, .csv, or .txt suffix "
            "or pass format explicitly."
        )
    return inferred


class _AtomicDestination(AbstractContextManager[Path]):
    """Own a temporary sibling file until validated output can be published.

    Use as a context manager, write to the returned temporary path, close the
    writer, then call publish(). A sibling stays on the destination filesystem
    so replacement can be atomic. Exiting always removes this object's leftover
    temporary file, while an existing final destination remains intact on failure.
    """

    def __init__(self, destination: Path, *, overwrite: bool) -> None:
        """Remember the final destination and the explicit overwrite policy.

        No file is created until __enter__; this keeps validation and allocation
        separate. Each context owns at most one temporary path.
        """
        self.destination = destination
        self.overwrite = overwrite
        self.temporary: Path | None = None
        self.published = False

    def __enter__(self) -> Path:
        """Create a private sibling file after checking the destination directory.

        Return its Path for the writer. Reject an existing destination when
        overwrite is false; publish() repeats the no-clobber guarantee against races.
        """
        parent = self.destination.parent
        if not parent.is_dir():
            raise IncompatibleDataError(
                f"Destination directory does not exist: {parent}."
            )
        if self.destination.exists() and not self.overwrite:
            raise OutputExistsError(f"Destination already exists: {self.destination}.")
        descriptor, name = tempfile.mkstemp(
            dir=parent,
            prefix=f".{self.destination.name}.",
            suffix=".tmp",
        )
        os.close(descriptor)
        self.temporary = Path(name)
        return self.temporary

    def publish(self) -> None:
        """Expose complete output only after validation and writer closure.

        Replace atomically when overwrite is allowed. Otherwise link the temporary
        file to the final name: unlike a preflight existence check, the link refuses
        a destination concurrently created by another process. Translate publication
        failures into OutputExistsError or CorruptedFileError.
        """
        if self.temporary is None:
            raise RuntimeError("Atomic destination has not been entered.")
        try:
            if self.overwrite:
                os.replace(self.temporary, self.destination)
            else:
                # An existence check followed by rename has a race. Linking
                # publishes only if the destination name is still unoccupied.
                os.link(self.temporary, self.destination)
                self.temporary.unlink()
        except FileExistsError as error:
            raise OutputExistsError(
                f"Destination was created during conversion: {self.destination}."
            ) from error
        except OSError as error:
            raise CorruptedFileError(
                f"Unable to publish destination {self.destination}: {error}."
            ) from error
        self.published = True

    def __exit__(self, *exc_info: object) -> None:
        """Remove only this context's remaining temporary file on success or failure.

        Never delete the final destination. Cleanup errors are suppressed to avoid
        hiding the original scientific or write failure.
        """
        if self.temporary is not None and self.temporary.exists():
            with suppress(OSError):
                self.temporary.unlink()


def _write_frame(dataframe: pd.DataFrame, path: Path, format: OutputFormat) -> None:
    """Serialize an already validated frame using the fixed canonical dialect.

    Parquet omits the pandas index; CSV/TXT use UTF-8, decimal point, a header
    and comma/tab delimiters. Wrap filesystem and Arrow failures as
    CorruptedFileError. The caller controls atomic publication.
    """
    try:
        if format == "parquet":
            table = pa.Table.from_pandas(dataframe, preserve_index=False)
            pq.write_table(table, path)
            return
        separator = "," if format == "csv" else "\t"
        dataframe.to_csv(
            path,
            sep=separator,
            decimal=".",
            encoding="utf-8",
            header=True,
            index=False,
        )
    except (OSError, pa.ArrowInvalid, pa.ArrowTypeError) as error:
        raise CorruptedFileError(
            f"Unable to write {format} output: {error}."
        ) from error


def write(
    dataframe: pd.DataFrame,
    destination: str | PathLike[str],
    *,
    format: OutputFormat | None = None,
    overwrite: bool = False,
) -> Path:
    """Validate and atomically save a complete standardized DataFrame.

    Use for a frame already held in memory. Validation preserves missing rows
    and rejects incompatible schema or time order. A temporary file in the same
    directory prevents a partial result from becoming the destination.

    Args:
        dataframe: Canonical columns in canonical order; values convertible to
            float64. No scientific column recognition is performed here.
        destination: File path; its parent directory must already exist.
        format: Explicit "parquet", "csv" or "txt"; otherwise infer the suffix.
        overwrite: Permit replacing an existing file only after successful writing.

    Returns:
        The destination Path. CSV uses commas; TXT uses tabs; neither writes an index.

    Raises:
        IncompatibleDataError: The schema, values or time violate the contract.
        UnsupportedFormatError: The output format is unsupported.
        OutputExistsError: The destination exists and overwrite is false.
        OSError: The directory or output cannot be written.

    Warns:
        MissingValueWarning: Missing measurements are retained in the output.

    Examples:
        >>> import battread
        >>> frame = battread.read("measurement.csv")  # doctest: +SKIP
        >>> battread.write(frame, "standardized.parquet")  # doctest: +SKIP
    """
    target = Path(destination)
    output_format = _output_format(target, format)
    canonical = coerce_canonical(dataframe)
    atomic = _AtomicDestination(target, overwrite=overwrite)
    with atomic as temporary:
        _write_frame(canonical, temporary, output_format)
        atomic.publish()
    return target


class _StreamingSink(AbstractContextManager["_StreamingSink"]):
    """Define the context-managed output boundary used by convert().

    Adapters accept canonical chunks and own writer resources; they do not
    choose scientific columns or publish the final destination themselves.
    """

    def write_chunk(self, dataframe: pd.DataFrame) -> None:
        """Require concrete sinks to append one canonical pandas chunk.

        The caller has already standardized the rows. Implementations must retain
        row order and missing cells without adding an index column.
        """
        raise NotImplementedError


class _ParquetSink(_StreamingSink):
    """Append canonical chunks as Parquet row groups without a full-result copy.

    The first chunk establishes the Arrow schema. The context closes the
    writer before the atomic destination is published.
    """

    def __init__(self, path: Path) -> None:
        """Store the temporary output path and defer schema-dependent writer
        creation."""
        self.path = path
        self.writer: pq.ParquetWriter | None = None

    def __enter__(self) -> "_ParquetSink":
        """Return the sink; the first chunk, not context entry, defines its schema."""
        return self

    def write_chunk(self, dataframe: pd.DataFrame) -> None:
        """Convert one pandas chunk to Arrow and append it without its index.

        Create the ParquetWriter on the first chunk and reuse it for later groups.
        The caller is responsible for whole-source validation before publication.
        """
        table = pa.Table.from_pandas(dataframe, preserve_index=False)
        if self.writer is None:
            self.writer = pq.ParquetWriter(self.path, table.schema)
        self.writer.write_table(table)

    def __exit__(self, *exc_info: object) -> None:
        """Close any created writer so footer metadata is complete before
        publication."""
        if self.writer is not None:
            self.writer.close()


class _TextSink(_StreamingSink):
    """Stream the library's fixed CSV/TXT dialect with exactly one header.

    Use only for canonical chunks; retained NaN cells become empty text fields.
    Keep the file handle open across chunks to avoid repeated headers.
    """

    def __init__(self, path: Path, format: Literal["csv", "txt"]) -> None:
        """Select comma or tab output and remember that the first chunk needs a
        header."""
        self.path = path
        self.separator = "," if format == "csv" else "\t"
        self.stream: IO[str] | None = None
        self.first = True

    def __enter__(self) -> "_TextSink":
        """Open the temporary UTF-8 destination and return the reusable text sink."""
        self.stream = self.path.open("w", encoding="utf-8", newline="")
        return self

    def write_chunk(self, dataframe: pd.DataFrame) -> None:
        """Append one chunk, emitting canonical column names only on the first call.

        Require an entered context. Never serialize the pandas index or change
        the decimal marker; these choices make read-back deterministic.
        """
        if self.stream is None:
            raise RuntimeError("Text sink has not been entered.")
        dataframe.to_csv(
            self.stream,
            sep=self.separator,
            decimal=".",
            header=self.first,
            index=False,
        )
        self.first = False

    def __exit__(self, *exc_info: object) -> None:
        """Close the text stream before the owning context publishes its destination."""
        if self.stream is not None:
            self.stream.close()


def _sink(path: Path, format: OutputFormat) -> _StreamingSink:
    """Create the format-specific streaming sink for a temporary destination.

    Scientific validation and final publication stay in convert(), keeping
    serialization concerns separate from ingestion.
    """
    if format == "parquet":
        return _ParquetSink(path)
    return _TextSink(path, format)


def convert(
    source: str | PathLike[str],
    destination: str | PathLike[str],
    *,
    format: OutputFormat | None = None,
    overwrite: bool = False,
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
) -> Path:
    """Read, standardize and atomically save a source without collecting chunks.

    Use for file-to-file conversion. Reader state spans all chunks, preserving
    time normalization and capacity reconstruction across boundaries. The final
    destination is published only after successful exhaustion of the input.
    Streaming readers, including MPR, bound source/tabular buffers;
    Neware binary checkpoint metadata can grow with file length.

    Args:
        source: Input path accepted by read().
        destination: Canonical output path in an existing directory.
        format: "parquet", "csv" or "txt"; inferred from the output suffix if absent.
        overwrite: Replace an existing destination after successful conversion.
        chunk_size: Positive maximum number of rows per standardized chunk.
        reader: Optional registered reader name.
        columns: Explicit semantic-to-source selectors, as for read().
        units: Explicit semantic-to-unit declarations, as for read().
        capacity_kind: Established cumulative_signed or delta_signed semantics.
        capacity_interval: Previous or next interval alignment for delta capacity.
        autodetect: Allow conservative automatic recognition of unspecified fields.
        sep: Explicit text delimiter, when supported by the reader.
        decimal: Explicit text decimal separator.
        encoding: Explicit text encoding.
        header: Text header row, "infer", or None for headerless input.
        skiprows: Number of leading physical text lines to skip.

    Returns:
        The completed destination Path.

    Raises:
        DataStandardizationError: Any reader, recognition or validation failure.
        OutputExistsError: The destination exists and overwrite is false.
        OSError: Input or output I/O fails.

    Warns:
        MissingValueWarning: Missing rows are preserved, with counts aggregated by the
            reader.
        MalformedValueWarning: Nonempty malformed numeric values are retained as NaN.

    Examples:
        >>> import battread
        >>> battread.convert("measurement.mpt", "standardized.parquet",
        ...                  chunk_size=100_000)  # doctest: +SKIP
    """
    target = Path(destination)
    output_format = _output_format(target, format)
    chunks: Iterator[pd.DataFrame] = iter_read(
        source,
        chunk_size=chunk_size,
        reader=reader,
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
    atomic = _AtomicDestination(target, overwrite=overwrite)
    with atomic as temporary:
        try:
            with _sink(temporary, output_format) as sink:
                for chunk in chunks:
                    sink.write_chunk(chunk)
        except (OSError, pa.ArrowInvalid, pa.ArrowTypeError) as error:
            raise CorruptedFileError(
                f"Unable to stream {output_format} output: {error}."
            ) from error
        atomic.publish()
    return target
