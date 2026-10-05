# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Type the narrow pandas boundary consistently across supported NumPy versions.

Older pandas/NumPy stubs leave parts of to_numpy and to_numeric unspecified.
These protocols describe only the calls actually used by battread. They do not
replace pandas parsing, change values, or disable strict application checking.
Scientific dtype and schema validation remains with the calling code.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray


class _ArraySource(Protocol):
    """Describe pandas' existing array-export interface without incomplete stubs."""

    def to_numpy(self, dtype: object = None, copy: bool = False) -> NDArray[Any]:
        """Return the existing pandas array export with its requested dtype/copy.

        The dtype is deliberately generic here: callers requesting float64
        establish the scientific type, while coercion callers retain the original
        values before performing their existing numeric conversion.
        """
        ...


class _NumericParser(Protocol):
    """Describe the Series-to-Series coercing overload of pandas.to_numeric."""

    def __call__(
        self, arg: pd.Series[Any], *, errors: Literal["coerce"]
    ) -> pd.Series[Any]:
        """Parse one Series, retaining unparseable cells as missing values."""
        ...


class _PandasAPI(Protocol):
    """Expose only the pandas parser needed by the typed adapter boundary."""

    to_numeric: _NumericParser


def numpy_values(
    values: pd.Series[Any] | pd.DataFrame,
    *,
    dtype: type[np.float64] | None = None,
    copy: bool = False,
) -> NDArray[Any]:
    """Export a pandas Series/frame using its original to_numpy implementation.

    Pass dtype=np.float64 only where the existing caller already requested it.
    With dtype=None, preserve pandas' inferred array and missing-value behavior.
    copy=False retains pandas' default allocation policy; it is not a promise
    that extension arrays can always be exported without allocating.
    The returned generic array is refined by callers after dtype validation.
    """
    return cast(_ArraySource, values).to_numpy(dtype=dtype, copy=copy)


def numeric_values(values: pd.Series[Any]) -> NDArray[np.float64]:
    """Apply pandas numeric coercion and export its result as float64.

    Used for selected delimited columns after decimal/clock normalization.
    This delegates to the same errors="coerce" parser as before, retaining
    malformed cells as NaN for the caller's structured warning. The module
    protocol exposes the documented callable instead of an
    incomplete upstream overload; it does not select another parser.
    """
    parser = cast(_PandasAPI, pd).to_numeric
    return cast(
        NDArray[np.float64],
        numpy_values(parser(values, errors="coerce"), dtype=np.float64),
    )
