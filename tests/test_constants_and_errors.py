# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for constants and errors.

Run with pytest from the project root. Fixtures establish controlled inputs;
assertions document the expected scientific and API behavior.
"""

import pytest

from battread import CANONICAL_COLUMNS, SCHEMA_VERSION
from battread.constants import CANONICAL_DTYPES, CANONICAL_UNITS
from battread.exceptions import (
    AmbiguousColumnError,
    CorruptedFileError,
    CurrentReconstructionError,
    DataStandardizationError,
    IncompatibleDataError,
    InvalidUnitError,
    MissingColumnError,
    MissingDependencyError,
    NonMonotonicTimeError,
    OutputExistsError,
    UnknownUnitError,
    UnsupportedFormatError,
)
from battread.warnings import (
    DataStandardizationWarning,
    MissingValueWarning,
    PartialRecoveryWarning,
)


def test_canonical_schema_constants_are_immutable_and_complete() -> None:
    """Verify that canonical schema constants are immutable and complete.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    assert CANONICAL_COLUMNS == ("time_s", "current_mA", "voltage_V")
    assert dict(CANONICAL_DTYPES) == {
        "time_s": "float64",
        "current_mA": "float64",
        "voltage_V": "float64",
    }
    assert dict(CANONICAL_UNITS) == {
        "time_s": "s",
        "current_mA": "mA",
        "voltage_V": "V",
    }
    assert SCHEMA_VERSION == "0.1"
    with pytest.raises(TypeError):
        CANONICAL_UNITS["time_s"] = "ms"  # type: ignore[index]


@pytest.mark.parametrize(
    "exception_type",
    [
        UnsupportedFormatError,
        MissingColumnError,
        AmbiguousColumnError,
        UnknownUnitError,
        InvalidUnitError,
        CurrentReconstructionError,
        NonMonotonicTimeError,
        IncompatibleDataError,
        CorruptedFileError,
        MissingDependencyError,
        OutputExistsError,
    ],
)
def test_domain_exceptions_share_package_base(
    exception_type: type[DataStandardizationError],
) -> None:
    """Verify that domain exceptions share package base.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    assert issubclass(exception_type, DataStandardizationError)


def test_warning_hierarchy_uses_standard_user_warnings() -> None:
    """Verify that warning hierarchy uses standard user warnings.

    Run with pytest; the assertions specify the expected measurements, preserved
    state or failure conditions for this regression.
    """
    assert issubclass(DataStandardizationWarning, UserWarning)
    assert issubclass(MissingValueWarning, DataStandardizationWarning)
    assert issubclass(PartialRecoveryWarning, DataStandardizationWarning)
