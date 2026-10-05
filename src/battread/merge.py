# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Merge already-standardized sequential acquisitions."""

import logging
from collections.abc import Iterable
from typing import cast, overload

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from battread._pandas import numpy_values
from battread.constants import TIME_COLUMN
from battread.exceptions import IncompatibleDataError
from battread.validation import validate_standardized

logger = logging.getLogger(__name__)


def _last_finite(values: NDArray[np.float64]) -> float:
    """Return the final finite endpoint of an already validated time array.

    Missing trailing rows remain in the dataset; only the endpoint used for
    segment placement is selected. The caller guarantees at least one finite time.
    """
    finite = values[np.isfinite(values)]
    return float(finite[-1])


def _first_finite(values: NDArray[np.float64]) -> float:
    """Return the initial finite endpoint without dropping leading missing rows.

    The input must already contain finite time. Merge uses this value only
    for calculating a shift, never to truncate the source segment.
    """
    finite = values[np.isfinite(values)]
    return float(finite[0])


def _last_positive_adjacent_interval(
    values: NDArray[np.float64],
) -> float | None:
    """Find the preceding segment's last usable bridge interval, or None.

    Inspect adjacent original rows from the end. Both endpoints must be
    finite and their difference positive; never bridge across a missing row
    or infer an interval from duplicate times.
    """
    for index in range(values.size - 2, -1, -1):
        left = values[index]
        right = values[index + 1]
        if np.isfinite(left) and np.isfinite(right):
            difference = float(right - left)
            if difference > 0:
                return difference
    return None


def _first_positive_adjacent_interval(
    values: NDArray[np.float64],
) -> float | None:
    """Find a fallback bridge interval from the next segment's adjacent rows.

    Scan forward and return the first strictly positive finite difference,
    or None. Keeping original adjacency prevents inventing timing across NaN gaps.
    """
    for index in range(values.size - 1):
        left = values[index]
        right = values[index + 1]
        if np.isfinite(left) and np.isfinite(right):
            difference = float(right - left)
            if difference > 0:
                return difference
    return None


@overload
def merge(datasets: Iterable[pd.DataFrame]) -> pd.DataFrame: ...


@overload
def merge(datasets: pd.DataFrame) -> pd.DataFrame: ...


def merge(datasets: Iterable[object] | pd.DataFrame) -> pd.DataFrame:
    """Join already-standardized DataFrames in the caller's acquisition order.

    Each later segment is shifted to follow the preceding segment by its last
    positive interval between adjacent finite rows. If that interval is absent,
    use the next segment's first positive adjacent interval; fail if neither
    exists. Missing timestamps never supply an inferred sampling interval.
    This operation copies frames and collects the result in memory.

    Args:
        datasets: Nonempty iterable of canonical DataFrames. Read input files
            with read() first; a single DataFrame must be wrapped in an iterable.

    Returns:
        A new float64 canonical DataFrame with a fresh RangeIndex. Current,
        voltage and missing rows are preserved; input frames are not modified.

    Raises:
        IncompatibleDataError: Inputs are invalid or a join interval is unavailable.

    Warns:
        MissingValueWarning: Missing values remain in the combined data.

    Examples:
        >>> import battread
        >>> frames = [battread.read(p) for p in ["first.mpt", "second.csv"]]
        ... # doctest: +SKIP
        >>> combined = battread.merge(frames)  # doctest: +SKIP
    """
    if isinstance(datasets, pd.DataFrame):
        raise IncompatibleDataError(
            "merge() expects an iterable of canonical DataFrames, "
            "not one DataFrame directly."
        )

    candidates = list(datasets)
    if not candidates:
        raise IncompatibleDataError("merge() requires at least one dataset.")

    parts: list[pd.DataFrame] = []
    for index, dataframe in enumerate(candidates):
        if not isinstance(dataframe, pd.DataFrame):
            raise IncompatibleDataError(
                f"Merge input {index} is not a pandas DataFrame."
            )
        try:
            validate_standardized(dataframe, emit_warnings=False)
        except IncompatibleDataError as error:
            raise type(error)(f"Merge input {index} is invalid: {error}") from error
        parts.append(dataframe)

    if len(parts) == 1:
        result = parts[0].copy(deep=True)
        validate_standardized(result)
        return result

    shifted_parts: list[pd.DataFrame] = [parts[0].copy(deep=True)]
    for index in range(1, len(parts)):
        previous_source_times = cast(
            NDArray[np.float64],
            numpy_values(parts[index - 1][TIME_COLUMN], dtype=np.float64, copy=False),
        )
        next_source_times = cast(
            NDArray[np.float64],
            numpy_values(parts[index][TIME_COLUMN], dtype=np.float64, copy=False),
        )
        bridge = _last_positive_adjacent_interval(previous_source_times)
        if bridge is None:
            bridge = _first_positive_adjacent_interval(next_source_times)
        if bridge is None:
            raise IncompatibleDataError(
                "Cannot merge datasets "
                f"{index - 1} and {index}: neither adjacent dataset contains "
                "a positive interval between adjacent finite time rows."
            )

        previous_shifted_times = cast(
            NDArray[np.float64],
            numpy_values(shifted_parts[-1][TIME_COLUMN], dtype=np.float64, copy=False),
        )
        offset = (
            _last_finite(previous_shifted_times)
            + bridge
            - _first_finite(next_source_times)
        )
        shifted = parts[index].copy(deep=True)
        shifted[TIME_COLUMN] = shifted[TIME_COLUMN] + offset
        shifted_parts.append(shifted)

    result = pd.concat(shifted_parts, ignore_index=True)
    validate_standardized(result)
    logger.debug("Merged %d canonical datasets into %d rows.", len(parts), len(result))
    return result
