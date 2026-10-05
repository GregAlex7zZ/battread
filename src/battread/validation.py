# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Validation for complete canonical DataFrames."""

import logging
import warnings as stdlib_warnings
from collections.abc import Mapping
from typing import cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from battread._pandas import numpy_values
from battread.constants import CANONICAL_COLUMNS, TIME_COLUMN
from battread.exceptions import (
    DataStandardizationError,
    IncompatibleDataError,
    NonMonotonicTimeError,
)
from battread.warnings import MissingValueWarning

logger = logging.getLogger(__name__)


def _missing_counts(dataframe: pd.DataFrame) -> Mapping[str, int]:
    """Count retained NaN cells by canonical column for structured warnings.

    Return only columns with a nonzero count. Call after schema validation;
    this reports data quality without modifying or deleting scientific rows.
    """
    counts: dict[str, int] = {}
    for column in CANONICAL_COLUMNS:
        count = int(dataframe[column].isna().sum())
        if count:
            counts[column] = count
    return counts


def validate_standardized(
    dataframe: object,
    *,
    emit_warnings: bool = True,
) -> None:
    """Validate a complete canonical DataFrame without modifying it.

    Args:
        dataframe: Candidate complete standardized dataset.
        emit_warnings: Emit a structured warning when missing values are retained.

    Raises:
        IncompatibleDataError: If the schema, dtype, finite-value, or origin
            requirements are not satisfied.
        NonMonotonicTimeError: If finite time moves backwards.
    """
    if not isinstance(dataframe, pd.DataFrame):
        raise IncompatibleDataError(
            "Canonical data must be provided as a pandas DataFrame."
        )

    actual_columns = tuple(dataframe.columns)
    if actual_columns != CANONICAL_COLUMNS:
        raise IncompatibleDataError(
            "Canonical columns must be exactly "
            f"{list(CANONICAL_COLUMNS)!r} in that order; "
            f"received {list(actual_columns)!r}."
        )
    if dataframe.empty:
        raise IncompatibleDataError("Canonical datasets must contain at least one row.")

    invalid_dtypes = {
        column: str(dataframe[column].dtype)
        for column in CANONICAL_COLUMNS
        if dataframe[column].dtype != np.dtype(np.float64)
    }
    if invalid_dtypes:
        details = ", ".join(
            f"{column}={dtype}" for column, dtype in invalid_dtypes.items()
        )
        raise IncompatibleDataError(
            f"Canonical columns must use float64 dtype; received {details}."
        )

    arrays: dict[str, NDArray[np.float64]] = {
        column: cast(
            NDArray[np.float64],
            numpy_values(dataframe[column], dtype=np.float64, copy=False),
        )
        for column in CANONICAL_COLUMNS
    }
    infinite_columns = [
        column for column, values in arrays.items() if np.isinf(values).any()
    ]
    if infinite_columns:
        raise IncompatibleDataError(
            "Canonical data contains infinity in "
            f"{', '.join(infinite_columns)}; infinity is not a missing value."
        )

    finite_time = arrays[TIME_COLUMN][np.isfinite(arrays[TIME_COLUMN])]
    if finite_time.size == 0:
        raise IncompatibleDataError(
            "Canonical time must contain at least one finite value."
        )
    if finite_time[0] != 0.0:
        raise IncompatibleDataError(
            "The first finite canonical time must be 0 seconds; "
            f"received {finite_time[0]!r}."
        )
    if (finite_time[1:] < finite_time[:-1]).any():
        raise NonMonotonicTimeError(
            "Finite canonical time moves backwards; automatic repair is unsafe."
        )

    missing_counts = _missing_counts(dataframe)
    if emit_warnings and missing_counts:
        stdlib_warnings.warn(
            MissingValueWarning(missing_counts),
            stacklevel=2,
        )
    logger.debug("Validated canonical DataFrame with %d rows.", len(dataframe))


def is_standardized(value: object) -> bool:
    """Return whether *value* satisfies the complete canonical contract.

    Use this predicate to check a candidate without catching domain errors.
    For a diagnostic explanation, use validate_standardized() instead.

    Args:
        value: Any object; non-DataFrames return False.

    Returns:
        True only for a nonempty canonical float64 DataFrame with finite,
        zero-origin, nondecreasing time and no infinity. NaNs are permitted.
        This predicate emits no warnings and never changes its input.

    Examples:
        >>> import pandas as pd
        >>> frame = pd.DataFrame({"time_s": [0.0], "current_mA": [-1.0],
        ...                       "voltage_V": [3.7]})
        >>> is_standardized(frame)
        True
    """
    if not isinstance(value, pd.DataFrame):
        return False
    try:
        validate_standardized(value, emit_warnings=False)
    except DataStandardizationError:
        return False
    return True
