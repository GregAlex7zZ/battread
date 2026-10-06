# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bounded binary ingestion behind the Bio-Logic adapter's optional backend.

Galvani supplies module-header decoding and field definitions, not its full-file
MPRfile constructor. Small metadata reads establish a validated source layout;
NumPy then reads a bounded number of structured records from an ordinary file.
No full-file mapping is retained, keeping resident pages and Windows committed
allocations independent of total measurement-payload size.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from os import fstat
from pathlib import Path
from struct import error as StructError
from struct import unpack_from
from typing import BinaryIO, Protocol, SupportsInt, cast

import numpy as np
from numpy.typing import NDArray

from battread.exceptions import (
    CorruptedFileError,
    IncompatibleDataError,
    UnsupportedFormatError,
)

MPR_MAGIC = b"BIO-LOGIC MODULAR FILE\x1a".ljust(48) + b"\x00" * 4
_MAX_BINARY_BYTES = 8 * 1024**2
_RETAINED_MODULES = {b"VMP Set   ", b"VMP data  ", b"VMP loop  ", b"VMP LOG   "}
# Explicit yadg definitions, not its generic unknown-column fallback. Impedance
# and counter-electrode values are outside our canonical schema; see the MPR
# developer guide for provenance and the conservative skip policy.
_OPAQUE_FIELD_BYTES = {115: 8, 116: 8, 175: 4, 176: 4, 177: 4, 182: 8, 215: 4}


class GalvaniSchema(Protocol):
    """Type only the lazy backend functions needed for schema and metadata.

    No backend arrays or metadata objects cross the reader's public boundary.
    The optional dependency remains responsible for known column-ID definitions.
    """

    def read_VMP_modules(
        self, stream: BinaryIO, read_module_data: bool = True
    ) -> Iterator[dict[str, object]]:
        """Yield mutable header descriptors; False seeks over scientific payloads."""
        ...

    def VMPdata_dtype_from_colIDs(
        self, identifiers: list[int]
    ) -> tuple[np.dtype[np.void], object]:
        """Resolve verified field widths, packed flags and duplicate-name suffixes."""
        ...

    def parse_BioLogic_date(self, value: bytes) -> date:
        """Apply the backend's existing date interpretation to metadata headers."""
        ...


@dataclass(frozen=True)
class _Module:
    """Keep only one small descriptor per relevant module, never its payload."""

    offset: int
    length: int
    version: int
    date_bytes: bytes


@dataclass(frozen=True)
class MPRLayout:
    """Validated measurement layout, with no open handles or full-source arrays.

    iter_arrays() opens the source lazily and closes on exhaustion/cancellation.
    A file identity/size/mtime stamp rejects replacement or mutation between
    metadata planning and ingestion. Each returned array owns only its batch.
    """

    path: Path
    data_offset: int
    rows: int
    dtype: np.dtype[np.void]
    stamp: tuple[int, int, int, int]

    def iter_arrays(self, rows_per_batch: int) -> Iterator[NDArray[np.void]]:
        """Read bounded arrays and reject short records or changes to the source.

        The byte cap additionally limits wide-record buffers. Closing this
        iterator releases its file immediately; arrays do not retain file handles.
        """
        if type(rows_per_batch) is not int or rows_per_batch <= 0:
            raise IncompatibleDataError("MPR batch size must be a positive integer.")
        batch_rows = min(
            rows_per_batch, max(1, _MAX_BINARY_BYTES // self.dtype.itemsize)
        )
        try:
            with self.path.open("rb") as stream:
                if _stamp(stream) != self.stamp:
                    raise CorruptedFileError(
                        "MPR source changed after metadata inspection."
                    )
                stream.seek(self.data_offset)
                remaining = self.rows
                while remaining:
                    count = min(remaining, batch_rows)
                    records: NDArray[np.void] = np.fromfile(
                        stream, dtype=self.dtype, count=count
                    )
                    if records.size != count:
                        raise CorruptedFileError("Truncated MPR measurement records.")
                    remaining -= count
                    yield records
                    # Release the previous buffer before allocating another.
                    del records
                if _stamp(stream) != self.stamp:
                    raise CorruptedFileError("MPR source changed during reading.")
        except (OSError, ValueError) as error:
            raise CorruptedFileError(
                f"Unable to stream Bio-Logic MPR: {error}."
            ) from error


def _stamp(stream: BinaryIO) -> tuple[int, int, int, int]:
    """Identify the opened source, its size and modification time without data reads."""
    stat = fstat(stream.fileno())
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _prefix(stream: BinaryIO, module: _Module, length: int) -> bytes:
    """Read an explicitly bounded metadata prefix within a validated module."""
    if length > module.length:
        raise ValueError("Truncated MPR module metadata")
    stream.seek(module.offset)
    value = stream.read(length)
    if len(value) != length:
        raise ValueError("Truncated MPR module metadata")
    return value


def _metadata(stream: BinaryIO, backend: GalvaniSchema) -> dict[bytes, _Module]:
    """Scan every module header while seeking over all scientific payloads.

    Reject truncated bounds, duplicate scientific/settings modules and malformed
    trailing headers. Retain only the four module categories used by Galvani.
    """
    size = _stamp(stream)[2]
    if stream.read(len(MPR_MAGIC)) != MPR_MAGIC:
        raise ValueError("Invalid magic for .mpr file")
    modules: dict[bytes, _Module] = {}
    for description in backend.read_VMP_modules(stream, read_module_data=False):
        offset = int(cast(SupportsInt, description["offset"]))
        length = int(cast(SupportsInt, description["length"]))
        # Galvani's header fields are NumPy uint32 scalars. Its generator seeks
        # after yielding this dictionary; normalize arithmetic to Python ints so
        # offsets beyond 4 GiB cannot overflow or wrap on generator resumption.
        description["offset"] = offset
        description["length"] = length
        if offset < 0 or length < 0 or offset + length > size:
            raise ValueError("Truncated MPR module payload")
        name = cast(bytes, description["shortname"])
        if name in _RETAINED_MODULES:
            if name in modules:
                raise ValueError(f"Duplicate MPR module {name!r}")
            modules[name] = _Module(
                offset,
                length,
                int(cast(SupportsInt, description["version"])),
                cast(bytes, description["date"]),
            )
    if b"VMP Set   " not in modules or b"VMP data  " not in modules:
        raise ValueError("MPR requires exactly one settings and one measurement module")
    return modules


def _measurement(
    stream: BinaryIO, module: _Module, backend: GalvaniSchema
) -> tuple[int, int, np.dtype[np.void]]:
    """Validate known data versions and decode only their small field-ID headers.

    Offsets and reserved-header checks reproduce Galvani 0.5's supported layouts:
    version 0 (legacy and newer encoding), 2 and 3. Unknown layouts never fall
    back to inferred widths. The complete payload must match the declared count.
    """
    first = _prefix(stream, module, 6)
    rows = int(unpack_from("<I", first)[0])
    columns = first[4]
    if not columns:
        raise ValueError("MPR measurement schema contains no fields")
    if module.version == 0:
        if first[5]:
            offset = 100
            header = _prefix(stream, module, offset)
            end = 5 + columns
            identifiers = list(header[5:end])
            padding = header[end:100]
        else:
            offset = 1007
            header = _prefix(stream, module, offset)
            end = 5 + 2 * columns
            identifiers = list(header[6:end:2])
            padding = header[6 + 2 * columns : 1006]
    elif module.version in {2, 3}:
        offset = 405 if module.version == 2 else 406
        header = _prefix(stream, module, offset)
        end = 5 + 2 * columns
        if end > 405:
            raise ValueError("MPR field-ID table overlaps measurement records")
        identifiers = [
            int(value) for value in unpack_from("<" + "H" * columns, header, 5)
        ]
        padding = header[end:405]
    else:
        raise ValueError(f"Unrecognised version for MPR data module: {module.version}")
    if len(identifiers) != columns or end > offset or any(padding):
        raise ValueError("Invalid MPR field-ID or reserved-header bytes")
    dtype = _record_dtype(identifiers, backend)
    if not dtype.names or dtype.itemsize <= 0:
        raise ValueError("Backend returned no structured scientific table")
    if module.length - offset != rows * dtype.itemsize:
        raise ValueError(
            "MPR payload length does not match declared measurement records"
        )
    return module.offset + offset, rows, dtype


def _record_dtype(identifiers: list[int], backend: GalvaniSchema) -> np.dtype[np.void]:
    """Delegate known fields and insert verified, non-scientific opaque padding.

    yadg's explicit definitions establish widths for the allowlisted impedance
    and counter-electrode fields. Retain opaque bytes rather than introducing
    scientific candidates. All other unknown IDs still fail.
    Prefix sizes from Galvani preserve its shared flag byte and duplicate names;
    its global schema is never patched. See the MPR developer guide for provenance.
    """
    if not any(identifier in _OPAQUE_FIELD_BYTES for identifier in identifiers):
        dtype, _ = backend.VMPdata_dtype_from_colIDs(identifiers)
        return dtype
    known: list[int] = []
    positions: dict[int, list[int]] = {}
    for identifier in identifiers:
        if identifier in _OPAQUE_FIELD_BYTES:
            size = backend.VMPdata_dtype_from_colIDs(known)[0].itemsize if known else 0
            positions.setdefault(size, []).append(identifier)
        else:
            known.append(identifier)
    dtype, _ = backend.VMPdata_dtype_from_colIDs(known)
    fields: list[tuple[str, np.dtype[np.generic]]] = []
    known_fields = cast(Mapping[str, tuple[np.dtype[np.generic], int]], dtype.fields)
    offset = 0
    skipped = 0
    for name in (*(dtype.names or ()), None):
        for identifier in positions.get(offset, []):
            skipped += 1
            fields.append(
                (
                    f"_ignored_mpr_{identifier}_{skipped}",
                    np.dtype(f"V{_OPAQUE_FIELD_BYTES[identifier]}"),
                )
            )
        if name is not None:
            field_dtype = known_fields[name][0]
            fields.append((name, field_dtype))
            offset += field_dtype.itemsize
    return np.dtype(fields)


def _validate_auxiliary(
    stream: BinaryIO, modules: Mapping[bytes, _Module], backend: GalvaniSchema
) -> None:
    """Preserve prior date, loop framing and LOG timestamp failure behavior.

    Loop indices and analysis metadata are not loaded or interpreted as cycling
    measurements. Only constant-size metadata needed for former validation is read.
    """
    start_date = backend.parse_BioLogic_date(modules[b"VMP Set   "].date_bytes)
    loop = modules.get(b"VMP loop  ")
    if loop is not None and (
        loop.version != 0 or loop.length < 4 or (loop.length - 4) % 4
    ):
        raise ValueError("Invalid MPR loop module version or record framing")
    log = modules.get(b"VMP LOG   ")
    if log is not None:
        backend.parse_BioLogic_date(log.date_bytes)
        prefix = _prefix(stream, log, 593)
        for offset in (465, 469, 473, 585):
            timestamp = float(unpack_from("<d", prefix, offset)[0])
            if 40000 < timestamp < 50000:
                break
        else:
            raise ValueError("Could not find timestamp in the LOG module")
        actual = datetime(1899, 12, 30) + timedelta(days=timestamp)
        if start_date != actual.date():
            raise ValueError("MPR settings date and LOG timestamp do not match")


def inspect_layout(path: Path, backend: GalvaniSchema) -> MPRLayout:
    """Validate the entire container structure without loading measurement values.

    Raises UnsupportedFormatError for unknown field definitions and
    CorruptedFileError for invalid/truncated containers. Returns a small layout
    descriptor; metadata inspection never allocates a full measurement array.
    """
    try:
        with path.open("rb") as stream:
            stamp = _stamp(stream)
            modules = _metadata(stream, backend)
            offset, rows, dtype = _measurement(stream, modules[b"VMP data  "], backend)
            _validate_auxiliary(stream, modules, backend)
            if _stamp(stream) != stamp:
                raise ValueError("MPR source changed during metadata inspection")
        return MPRLayout(path, offset, rows, dtype, stamp)
    except NotImplementedError as error:
        raise UnsupportedFormatError(
            f"Galvani cannot interpret this MPR field schema: {error}."
        ) from error
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AssertionError,
        StructError,
    ) as error:
        raise CorruptedFileError(f"Unable to parse Bio-Logic MPR: {error}.") from error
