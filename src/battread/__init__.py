# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Vendor-independent standardization of electrochemical cycling data."""

from importlib.metadata import PackageNotFoundError, version

from battread.api import detect_format, inspect, iter_read, read
from battread.constants import CANONICAL_COLUMNS, SCHEMA_VERSION
from battread.merge import merge
from battread.output import convert, write
from battread.validation import is_standardized

try:
    __version__ = version("battread")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.1.0"

__all__ = [
    "CANONICAL_COLUMNS",
    "SCHEMA_VERSION",
    "__version__",
    "convert",
    "detect_format",
    "inspect",
    "is_standardized",
    "iter_read",
    "merge",
    "read",
    "write",
]
