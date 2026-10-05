# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Canonical schema constants."""

from types import MappingProxyType
from typing import Final

TIME_COLUMN: Final = "time_s"
CURRENT_COLUMN: Final = "current_mA"
VOLTAGE_COLUMN: Final = "voltage_V"

CANONICAL_COLUMNS: Final = (TIME_COLUMN, CURRENT_COLUMN, VOLTAGE_COLUMN)
CANONICAL_DTYPES: Final = MappingProxyType(
    {
        TIME_COLUMN: "float64",
        CURRENT_COLUMN: "float64",
        VOLTAGE_COLUMN: "float64",
    }
)
CANONICAL_UNITS: Final = MappingProxyType(
    {
        TIME_COLUMN: "s",
        CURRENT_COLUMN: "mA",
        VOLTAGE_COLUMN: "V",
    }
)

SCHEMA_VERSION: Final = "0.1"
