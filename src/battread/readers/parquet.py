# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Dedicated canonical Parquet reader."""

# PyArrow does not publish complete type information for its Python boundary.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from battread.canonical import CanonicalStreamValidator, coerce_canonical
from battread.constants import CANONICAL_COLUMNS
from battread.exceptions import CorruptedFileError, IncompatibleDataError
from battread.readers.models import FormatInfo, ReaderCapabilities, ReadOptions
from battread.recognition.models import ColumnMatch, InspectionResult

_PARQUET_MAGIC = b"PAR1"


def _reject_options(options: ReadOptions) -> None:
    """Reject source reinterpretation options for an already canonical Parquet file.

    Mappings, units, capacity and text options could hide an invalid canonical
    schema, so the adapter validates the stored contract instead of repairing it.
    """
    defaults = ReadOptions()
    if options.columns or options.units:
        raise IncompatibleDataError(
            "Canonical Parquet does not accept column or unit overrides."
        )
    if options.capacity_kind is not None or options.capacity_interval is not None:
        raise IncompatibleDataError(
            "Canonical Parquet does not contain reconstruction capacity fields."
        )
    if options.autodetect is not defaults.autodetect:
        raise IncompatibleDataError(
            "Canonical Parquet does not support the autodetect option."
        )
    if (
        options.sep is not None
        or options.decimal is not None
        or options.encoding is not None
        or options.header != defaults.header
        or options.skiprows != defaults.skiprows
    ):
        raise IncompatibleDataError(
            "Text parsing options are unsupported for canonical Parquet."
        )


def _parquet_file(path: Path) -> pq.ParquetFile:
    """Open Parquet metadata and require exact ordered canonical column names.

    Return the Arrow file object for reading or batches. Wrap unreadable data
    as CorruptedFileError; schema mismatches raise IncompatibleDataError.
    """
    try:
        parquet = pq.ParquetFile(path)
    except (OSError, pa.ArrowInvalid, pa.ArrowTypeError) as error:
        raise CorruptedFileError(f"Invalid Parquet source {path}: {error}.") from error
    if tuple(parquet.schema_arrow.names) != CANONICAL_COLUMNS:
        raise IncompatibleDataError(
            "Canonical Parquet columns must be exactly "
            f"{list(CANONICAL_COLUMNS)!r} in that order."
        )
    return parquet


def _matches() -> tuple[ColumnMatch, ...]:
    """Describe the exact canonical Parquet fields as resolved inspection matches.

    Their names establish quantities and units; no generic label inference
    or scientific competition is needed for this already-standardized schema.
    """
    units = ("s", "mA", "V")
    quantities = ("time", "current", "voltage")
    return tuple(
        ColumnMatch(
            source_column=column,
            source_position=position,
            quantity=quantity,
            unit=unit,
            semantic=None,
            interval_alignment=None,
            state="resolved",
            confidence=0.95,
            evidence=("exact canonical Parquet schema",),
        )
        for position, (column, quantity, unit) in enumerate(
            zip(CANONICAL_COLUMNS, quantities, units, strict=True)
        )
    )


class CanonicalParquetReader:
    """Read only the library's canonical three-column Parquet schema.

    Register an instance with ReaderRegistry. Arrow batches support incremental
    input while pandas remains the output interface. This adapter does not guess
    scientific columns in arbitrary Parquet files; canonical names, types and
    stream-wide time constraints must hold.
    """

    name = "parquet"
    capabilities = ReaderCapabilities(
        streaming=True, text_options=False, formats=("parquet",)
    )

    def detect(self, path: Path) -> FormatInfo | None:
        """Recognize Parquet framing without loading its full table.

        Schema and canonical values are validated by inspection/read operations;
        magic alone does not establish a valid standardized dataset.
        """
        try:
            with path.open("rb") as stream:
                prefix = stream.read(4)
                stream.seek(-4, 2)
                suffix = stream.read(4)
        except (OSError, ValueError):
            return None
        if prefix != _PARQUET_MAGIC or suffix != _PARQUET_MAGIC:
            return None
        return FormatInfo(
            "parquet",
            self.name,
            1.0,
            ("Parquet magic bytes",),
        )

    def inspect(self, path: Path, options: ReadOptions) -> InspectionResult:
        """Validate canonical metadata and return fixed field evidence without data
        loading.

        Reject reinterpretation options and wrong column order. Full-value checks
        remain the responsibility of read() or complete iterator consumption.
        """
        _reject_options(options)
        _parquet_file(path)
        return InspectionResult(
            format="parquet",
            reader=self.name,
            columns=_matches(),
            current_reconstruction_required=False,
        )

    def read(self, path: Path, options: ReadOptions) -> pd.DataFrame:
        """Load one canonical Parquet table, coerce numeric dtypes and validate it.

        Return a complete pandas frame with unchanged time origin and row order.
        This path uses full-result memory; batches are available via iter_read().
        """
        _reject_options(options)
        parquet = _parquet_file(path)
        try:
            dataframe = cast(pd.DataFrame, parquet.read().to_pandas())
        except (OSError, pa.ArrowInvalid, pa.ArrowTypeError) as error:
            raise CorruptedFileError(
                f"Unable to read Parquet data: {error}."
            ) from error
        return coerce_canonical(dataframe)

    def iter_read(
        self, path: Path, options: ReadOptions, *, chunk_size: int
    ) -> Iterator[pd.DataFrame]:
        """Prepare Arrow record batches with cross-batch canonical validation.

        Require validated default canonical options and a positive chunk size
        from the public boundary. Decoder buffers and row groups also consume RAM.
        """
        _reject_options(options)
        parquet = _parquet_file(path)
        return self._iter_batches(parquet, chunk_size)

    @staticmethod
    def _iter_batches(
        parquet: pq.ParquetFile, chunk_size: int
    ) -> Iterator[pd.DataFrame]:
        """Yield pandas batches validated as fragments of one canonical source.

        Carry first/previous finite times across batches and call finish() at
        exhaustion. Late failures are intentional; convert() must not publish
        output before that final check succeeds.
        """
        validator = CanonicalStreamValidator()
        try:
            for batch in parquet.iter_batches(batch_size=chunk_size):
                frame = cast(pd.DataFrame, batch.to_pandas())
                yield validator.validate_chunk(frame)
        except (OSError, pa.ArrowInvalid, pa.ArrowTypeError) as error:
            raise CorruptedFileError(
                f"Unable to stream Parquet data: {error}."
            ) from error
        validator.finish()
