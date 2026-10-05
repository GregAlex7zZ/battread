# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Extensible reader registry."""

from pathlib import Path

from battread.exceptions import UnsupportedFormatError
from battread.readers.base import Reader
from battread.readers.models import FormatInfo


class ReaderRegistry:
    """Select registered readers by explicit name or detection confidence."""

    def __init__(self) -> None:
        """Start an empty registry whose insertion order provides stable detection
        ties."""
        self._readers: dict[str, Reader] = {}

    def register(self, reader: Reader) -> None:
        """Register a structural Reader implementation under its unique name.

        Raise ValueError for duplicate names instead of silently replacing an
        adapter. Public API setup calls this once for each built-in reader.
        """
        if reader.name in self._readers:
            raise ValueError(f"Reader {reader.name!r} is already registered.")
        self._readers[reader.name] = reader

    def select(
        self, path: Path, requested: str | None = None
    ) -> tuple[Reader, FormatInfo]:
        """Choose an explicit adapter or the highest-confidence detected source.

        Accept an existing path and optional registered name; return (reader,
        FormatInfo). Explicit names still require the reader to recognize the
        file. Raise UnsupportedFormatError for unknown names or unsupported
        content; tied detection scores retain registration order.
        """
        if requested is not None:
            reader = self._readers.get(requested)
            if reader is None:
                choices = ", ".join(sorted(self._readers))
                raise UnsupportedFormatError(
                    f"Unknown reader {requested!r}. Registered readers: {choices}."
                )
            detected = reader.detect(path)
            if detected is None:
                raise UnsupportedFormatError(
                    f"Reader {requested!r} cannot safely interpret {path}."
                )
            return reader, detected

        detected_readers = [
            (reader, info)
            for reader in self._readers.values()
            if (info := reader.detect(path)) is not None
        ]
        if not detected_readers:
            raise UnsupportedFormatError(f"No registered reader supports {path}.")
        detected_readers.sort(key=lambda item: item[1].confidence, reverse=True)
        return detected_readers[0]
