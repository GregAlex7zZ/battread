# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Column recognition models and deterministic engine."""

from battread.recognition.engine import (
    inspection_result,
    recognize_columns,
    resolve_quantity,
)
from battread.recognition.labels import ParsedLabel, normalize_label, parse_label
from battread.recognition.models import ColumnMatch, InspectionResult, ReaderHint

__all__ = [
    "ColumnMatch",
    "InspectionResult",
    "ParsedLabel",
    "ReaderHint",
    "inspection_result",
    "normalize_label",
    "parse_label",
    "recognize_columns",
    "resolve_quantity",
]
