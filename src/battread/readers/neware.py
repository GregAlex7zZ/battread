# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

# Adapted third-party layouts retain their BSD-3-Clause notice below.
"""Strict Neware record adapters, isolated from backend postprocessing."""

# Record layouts adapted from NewareNDA, Copyright (c) 2022-2024 SES AI
# Corporation, BSD-3-Clause. See licenses/NewareNDA-BSD-3-Clause.txt.

# Vendor records reuse the internal canonical table pipeline.
# pyright: reportPrivateUsage=false

import math
import mmap
import struct
import zipfile
from collections.abc import Callable, Generator, Iterator
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import IO, Protocol, cast

import pandas as pd

from battread.exceptions import (
    CorruptedFileError,
    IncompatibleDataError,
    MissingDependencyError,
    UnsupportedFormatError,
)
from battread.readers.delimited import DelimitedReader, _inspection_matches, _TablePlan
from battread.readers.models import FormatInfo, ReaderCapabilities, ReadOptions
from battread.recognition.models import InspectionResult, ReaderHint

_COLUMNS = ("Timestamp", "Current(mA)", "Voltage")
_HINTS = (
    ReaderHint("Timestamp", "time", "s"),
    ReaderHint("Current(mA)", "current", "mA"),
    ReaderHint("Voltage", "voltage", "V"),
)
_PLAN = _TablePlan("", "", ".", None, _COLUMNS, 3, False)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_SPLIT = {
    11: ("<ixffff8xiiiih", 16, 1e-4, 1.0),
    14: ("<ixffff8xiiiih8s", 4, 1.0, 1000.0),
    16: ("<ixffff8xiiiih53s", 64, 1e-4, 1.0),
    17: ("<ixffff8xiiiih53s", 64, 1.0, 1000.0),
}


class _NDA(Protocol):
    """Describe the isolated optional backend's raw NDA decoder interface."""

    def _bytes_to_list(self, data: bytes) -> list[object]:
        """Decode one framed NDA29 record without backend sorting or deduplication."""
        ...

    def _bytes_to_list_BTS9(self, data: bytes) -> list[object]:
        """Decode the payload of an 88-byte BTS9 record after its four-byte prefix."""
        ...

    def _bytes_to_list_BTS91(self, data: bytes) -> list[object]:
        """Decode a supported BTS9.1 raw record with directly measured float fields."""
        ...


class _NDC(Protocol):
    """Describe only the full-record NDC decoder used at the adapter boundary."""

    def _bytes_to_list_ndc(self, data: bytes) -> list[object]:
        """Decode one full NDC measurement without high-level interpolation or
        analysis."""
        ...


def _backend(module: str) -> object:
    """Import a NewareNDA submodule only when binary support is actually requested.

    Return the module behind the local protocol. MissingDependencyError
    points to the neware extra; CSV ingestion never needs this import.
    """
    try:
        return import_module(f"NewareNDA.{module}")
    except ImportError as error:
        raise MissingDependencyError(
            'Neware support requires pip install "battread[neware]".'
        ) from error


def _options(options: ReadOptions) -> None:
    """Reject text-dialect settings for NDA/NDAX before decoding binary fields.

    Canonical column and unit overrides remain governed by the shared
    pipeline; text separators or skipped lines cannot reinterpret binary records.
    """
    if (
        options.sep is not None
        or options.decimal is not None
        or options.encoding is not None
        or options.header != "infer"
        or options.skiprows != 0
    ):
        raise IncompatibleDataError("Text parser options are unsupported for NDA/NDAX.")


def _decode(decoder: Callable[[bytes], list[object]], record: bytes) -> list[object]:
    """Decode one measurement while converting malformed/range failures to domain
    errors.

    Require a nonzero scientific index/status instead of accepting the backend's
    empty-list sentinel as permission to lose a row. Unknown hardware ranges
    or statuses are unsupported; malformed fields are corruption.
    """
    try:
        values = decoder(record)
    except KeyError as error:
        raise UnsupportedFormatError(
            f"NewareNDA does not recognize this hardware range or status: {error}."
        ) from error
    except (ValueError, TypeError, IndexError, OverflowError, struct.error) as error:
        raise CorruptedFileError(
            f"Malformed Neware scientific record: {error}."
        ) from error
    if not values or not values[0]:
        raise CorruptedFileError(
            "Neware scientific record has an invalid zero index/status."
        )
    return values


def _nda_layout(path: Path) -> tuple[int, int, int, bytes]:
    """Resolve a supported NDA header to version, start offset, width and framing.

    Use existing path bytes and a read-only mapping for NDA29's record search.
    Reject unsupported versions and absent/truncated framing before streaming.
    The returned profile does not imply support for every hardware variant.
    """
    with path.open("rb") as stream:
        header = stream.read(1112)
        if len(header) < 15 or header[:6] != b"NEWARE":
            raise CorruptedFileError("Invalid Neware NDA magic or truncated header.")
        version = header[14]
        if version == 29:
            with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
                offset = mapped.find(b"\x00\x00\x00\x00\x55\x00")
            if offset < 0:
                raise CorruptedFileError("NDA contains no framed scientific records.")
            return version, offset + 4, 86, b"\x55\x00"
        if version == 130:
            if len(header) < 1080:
                raise CorruptedFileError("Truncated NDA 130 data header.")
            if header[1024] == 0x55:
                return version, 1024, 56, header[1024:1026]
            return version, 1024, 88, header[1024:1030]
        raise UnsupportedFormatError(f"Unsupported NDA version {version}.")


def _nda_records(path: Path) -> Generator[tuple[datetime | None, float, float]]:
    """Stream timestamp/current/voltage triples in physical NDA record order.

    Skip only recognized auxiliary records, reserved padding or declared
    metadata footers. Unknown framing and truncated measurements fail; no sorting
    or scientific deduplication is allowed. Raw measured current retains its sign.
    """
    backend = cast(_NDA, _backend("NewareNDA"))
    version, offset, size, signature = _nda_layout(path)
    with path.open("rb") as stream:
        stream.seek(offset)
        while record := stream.read(size):
            if version == 130 and (
                record.startswith(b"\x81")
                or record.startswith(b"\x06\x00\xf0\x1d\x81\x00\x03\x00")
            ):
                break  # A declared metadata footer is not a measurement.
            if len(record) != size:
                raise CorruptedFileError("Truncated NDA scientific record.")
            if not any(record):
                continue  # Reserved zero padding, never a framed data row.
            if version == 29:
                if record[82:] != b"\x00" * 4:
                    raise CorruptedFileError("Invalid NDA 29 record trailer.")
                if record[0] == 0x65:
                    continue  # Auxiliary channels are outside the canonical schema.
                if not record.startswith(signature):
                    raise CorruptedFileError("Unknown NDA 29 record framing.")
                values = _decode(backend._bytes_to_list, record)
            elif size == 56:
                if not record.startswith(signature):
                    raise CorruptedFileError(
                        "Unsupported NDA 9.1 record framing/length."
                    )
                values = _decode(backend._bytes_to_list_BTS91, record)
            else:
                if record.startswith(b"\x00\x00\x00\x00\x65"):
                    continue
                if not record.startswith(signature):
                    raise CorruptedFileError("Unknown NDA 9.0 record framing.")
                values = _decode(backend._bytes_to_list_BTS9, record[4:])
            yield (
                cast(datetime, values[12]),
                float(cast(float, values[7])),
                float(cast(float, values[6])),
            )


def _blocks(stream: IO[bytes]) -> Iterator[bytes]:
    """Yield complete 4096-byte NDC blocks after the fixed header.

    Use a seekable binary stream. A partial final block is corruption, not a
    reason to drop its possible measurements silently.
    """
    stream.seek(4096)
    while block := stream.read(4096):
        if len(block) != 4096:
            raise CorruptedFileError("Truncated NDC block.")
        yield block


def _run_times(archive: zipfile.ZipFile, version: int) -> dict[int, datetime]:
    """Read recorded split-NDAX timestamp checkpoints keyed by measurement index.

    Validate a unique matching metadata member and millisecond/index ranges.
    Identical repeated checkpoints share one key; conflicting timestamps fail.
    Return recorded datetimes only, never interpolated scientific time.
    """
    if archive.namelist().count("data_runInfo.ndc") != 1:
        raise UnsupportedFormatError("Split NDAX lacks recorded timestamp metadata.")
    layout, trailer, _, _ = _SPLIT[version]
    result: dict[int, datetime] = {}
    with archive.open("data_runInfo.ndc") as stream:
        header = stream.read(4096)
        if len(header) != 4096 or header[0] != 18 or header[2] != version:
            raise CorruptedFileError("Inconsistent NDAX timestamp schema.")
        for block in _blocks(stream):
            for record in struct.iter_unpack(layout, block[132:-trailer]):
                index = int(record[8])
                if index == 0:
                    if any(record[:10]):
                        raise CorruptedFileError("Malformed NDAX timestamp checkpoint.")
                    continue
                if index < 0 or not 0 <= int(record[9]) < 1000:
                    raise CorruptedFileError(
                        "Invalid NDAX timestamp index/milliseconds."
                    )
                time = _EPOCH + timedelta(
                    seconds=int(record[6]), milliseconds=int(record[9])
                )
                if index in result and result[index] != time:
                    raise CorruptedFileError("Conflicting NDAX timestamp checkpoints.")
                result[index] = time
    return result


def _split_records(
    archive: zipfile.ZipFile, version: int
) -> Iterator[tuple[datetime | None, float, float]]:
    """Join split measurement slots to recorded times while retaining interior zeros.

    Scan primary blocks to locate trailing reserved padding, then stream
    (timestamp_or_None, current_mA, voltage_V). Missing checkpoints remain
    missing. The checkpoint dictionary consumes memory proportional to metadata
    count; unsupported ambiguity must not be repaired by interpolation.
    """
    times = _run_times(archive, version)
    if not times:
        raise CorruptedFileError("NDAX has no finite recorded timestamp.")
    _, _, voltage_scale, current_scale = _SPLIT[version]
    # Padding follows the last primary slot/checkpoint; retain interior zeros.
    last = max(times)
    with archive.open("data.ndc") as stream:
        count = 0
        for block in _blocks(stream):
            for voltage, current in struct.iter_unpack("<ff", block[132:-4]):
                count += 1
                if voltage != 0 or current != 0:
                    last = max(last, count)
    if last > count:
        raise CorruptedFileError("NDAX timestamp refers to an absent primary record.")
    with archive.open("data.ndc") as stream:
        index = 0
        for block in _blocks(stream):
            for voltage, current in struct.iter_unpack("<ff", block[132:-4]):
                index += 1
                if index > last:
                    return
                yield times.get(index), current * current_scale, voltage * voltage_scale


def _ndax_records(path: Path) -> Generator[tuple[datetime | None, float, float]]:
    """Validate the archive profile and stream supported full or split measurements.

    Require one data.ndc member and known NDC versions. Full-record decoders
    remain backend-local; split schemas use audited structural layouts. Translate
    archive, framing and decode errors without silently skipping unknown records.
    """
    backend = cast(_NDC, _backend("NewareNDAx"))
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.namelist().count("data.ndc") != 1:
                raise CorruptedFileError(
                    "NDAX requires one unambiguous data.ndc member."
                )
            with archive.open("data.ndc") as stream:
                header = stream.read(4096)
                if len(header) < 3 or header[0] != 1:
                    raise CorruptedFileError("Invalid NDC primary data header.")
                version = header[2]
                if version in _SPLIT:
                    yield from _split_records(archive, version)
                    return
                if version not in {2, 5}:
                    raise UnsupportedFormatError(f"Unsupported NDC version {version}.")
                if version == 2:
                    stream.seek(517)
                    records = iter(lambda: stream.read(94), b"")
                else:
                    records = (
                        block[start : start + 87]
                        for block in _blocks(stream)
                        for start in range(125, 4040, 87)
                    )
                for record in records:
                    if not any(record):
                        continue
                    if len(record) != (94 if version == 2 else 87):
                        raise CorruptedFileError("Truncated full NDC record.")
                    marker = 0 if version == 2 else 7
                    if record[marker] != 0x55:
                        raise CorruptedFileError("Unknown primary NDC record framing.")
                    values = _decode(backend._bytes_to_list_ndc, record)
                    yield (
                        cast(datetime, values[11]),
                        float(cast(float, values[6])),
                        float(cast(float, values[5])),
                    )
    except (
        zipfile.BadZipFile,
        OSError,
        EOFError,
        struct.error,
        OverflowError,
        RuntimeError,
    ) as error:
        raise CorruptedFileError(
            f"Invalid Neware NDAX container/records: {error}."
        ) from error


def _rows(
    records: Iterator[tuple[datetime | None, float, float]],
) -> Iterator[list[str]]:
    """Convert decoded triples to shared table rows with elapsed seconds.

    The first recorded datetime establishes the origin. Missing timestamps
    become empty cells, preserving rows; subtraction precedes float conversion
    to avoid precision loss from subtracting large epoch floats.
    """
    origin: datetime | None = None
    for timestamp, current, voltage in records:
        if timestamp is not None and origin is None:
            origin = timestamp
        time = (
            (timestamp - origin).total_seconds()
            if timestamp is not None and origin is not None
            else math.nan
        )
        yield [
            "" if math.isnan(value) else repr(value)
            for value in (time, current, voltage)
        ]


class NewareReader(DelimitedReader):
    """Decode experimental NDA/NDAX through isolated optional raw backend decoders.

    Register an instance with ReaderRegistry. Raw records preserve acquisition
    order; the adapter never interpolates, sorts or deduplicates scientific rows.
    iter_read() bounds record buffers, but checkpoint metadata may grow with the
    source. Unsupported framing fails explicitly. Neware CSV exports use the
    delimited reader and their verified Total Time profile instead.
    """

    name = "neware"
    capabilities = ReaderCapabilities(True, False, ("nda", "ndax"))

    def detect(self, path: Path) -> FormatInfo | None:
        """Recognize NDA magic or an NDAX archive member, with a suffix fallback.

        Return FormatInfo or None. Detection is not a promise that every binary
        layout is supported; strict framing validation occurs during ingestion.
        """
        with path.open("rb") as stream:
            magic = stream.read(6)
        if magic == b"NEWARE":
            return FormatInfo("nda", self.name, 1.0, ("NEWARE magic",))
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                if "data.ndc" in archive.namelist():
                    return FormatInfo(
                        "ndax", self.name, 1.0, ("NDAX data.ndc ZIP member",)
                    )
        if path.suffix.casefold() in {".nda", ".ndax"}:
            return FormatInfo(
                path.suffix[1:].casefold(),
                self.name,
                0.95,
                ("Neware extension; framing requires validation",),
            )
        return None

    def inspect(self, path: Path, options: ReadOptions) -> InspectionResult:
        """Validate the binary profile and expose authoritative field matches.

        Consume an initial decoded row and close resources. Split layouts scan
        metadata and primary blocks, so inspection is not a bounded-header operation.
        Current is directly measured; Neware capacity reconstruction is not inferred.
        """
        _options(options)
        information = self.detect(path)
        if information is None:
            raise UnsupportedFormatError(
                "Source is not a recognized Neware NDA/NDAX file."
            )
        records = (
            _nda_records(path) if information.format == "nda" else _ndax_records(path)
        )
        try:
            if next(records, None) is None:
                raise CorruptedFileError("Neware source contains no scientific rows.")
        finally:
            records.close()
        matches = _inspection_matches(_PLAN, options, vendor="neware", hints=_HINTS)
        return InspectionResult(
            information.format,
            self.name,
            matches,
            current_reconstruction_required=False,
        )

    def _iter_read(
        self, path: Path, options: ReadOptions, *, chunk_size: int, emit_missing: bool
    ) -> Iterator[pd.DataFrame]:
        """Feed strict binary measurement rows into the canonical table pipeline.

        Use verified timestamp/current/voltage hints, apply validated options and
        retain one time origin across chunks. Chunked output never enables the
        backend's interpolation, sorting, deduplication or cycle generation.
        """
        _options(options)
        information = self.detect(path)
        if information is None:
            raise UnsupportedFormatError(
                "Source is not a recognized Neware NDA/NDAX file."
            )
        records = (
            _nda_records(path) if information.format == "nda" else _ndax_records(path)
        )
        matches = _inspection_matches(_PLAN, options, vendor="neware", hints=_HINTS)
        return self._iter_table(
            _PLAN,
            options,
            matches,
            _rows(records),
            chunk_size=chunk_size,
            emit_missing=emit_missing,
        )
