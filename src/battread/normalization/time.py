# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Elapsed-time normalization."""

from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from battread.exceptions import IncompatibleDataError, NonMonotonicTimeError


def normalize_time(values: object) -> NDArray[np.float64]:
    """Copy seconds into elapsed time with the first finite timestamp at zero.

    Use after source units have been converted to seconds. Missing values stay
    in their original positions; finite timestamps must remain nondecreasing
    across missing rows. Duplicate timestamps are permitted, never sorted away.

    Args:
        values: One-dimensional numeric array-like time series in seconds.

    Returns:
        A new float64 array with the first finite value subtracted from each row.

    Raises:
        IncompatibleDataError: Values are nonnumeric, multidimensional, infinite
            or contain no finite timestamp.
        NonMonotonicTimeError: Finite time moves backwards.

    Examples:
        >>> normalize_time([10.0, 11.5, 13.0])
        array([0. , 1.5, 3. ])
    """
    try:
        result: NDArray[np.float64] = np.asarray(
            cast(Any, values), dtype=np.float64
        ).copy()
    except (TypeError, ValueError) as error:
        raise IncompatibleDataError(
            "Time values are not numerically compatible."
        ) from error

    if result.ndim != 1:
        raise IncompatibleDataError("Time values must be one-dimensional.")
    if np.isinf(result).any():
        raise IncompatibleDataError(
            "Time values contain positive or negative infinity."
        )

    finite = result[np.isfinite(result)]
    if finite.size == 0:
        raise IncompatibleDataError("Time must contain at least one finite value.")
    if (finite[1:] < finite[:-1]).any():
        raise NonMonotonicTimeError(
            "Finite time values move backwards; automatic repair is unsafe."
        )

    result -= finite[0]
    return result
