# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Canonical DataFrame coercion and streaming validation helpers."""

import warnings
from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from battread._pandas import numpy_values
from battread.constants import CANONICAL_COLUMNS, TIME_COLUMN
from battread.exceptions import IncompatibleDataError, NonMonotonicTimeError
from battread.validation import validate_standardized
from battread.warnings import MissingValueWarning


def coerce_canonical(dataframe: object, *, emit_warnings: bool = True) -> pd.DataFrame:
    """Copy canonical columns to float64 and validate without scientific repair.

    Used by writers for already-standardized data. This is not recognition:
    the three names and their order must already match the canonical schema.

    Args:
        dataframe: Nonempty DataFrame with time_s, current_mA and voltage_V.
        emit_warnings: Report retained missing values after validation.

    Returns:
        An independent float64 DataFrame preserving index and missing rows.

    Raises:
        IncompatibleDataError: Schema, numeric values or zero-origin time are invalid.
        NonMonotonicTimeError: Finite time moves backwards.
    """
    if not isinstance(dataframe, pd.DataFrame):
        raise IncompatibleDataError(
            "Canonical data must be provided as a pandas DataFrame."
        )
    columns = tuple(dataframe.columns)
    if columns != CANONICAL_COLUMNS:
        raise IncompatibleDataError(
            "Canonical columns must be exactly "
            f"{list(CANONICAL_COLUMNS)!r} in that order; received {list(columns)!r}."
        )
    result = dataframe.copy(deep=True)
    for column in CANONICAL_COLUMNS:
        try:
            values = np.asarray(numpy_values(dataframe[column]), dtype=np.float64)
        except (TypeError, ValueError) as error:
            raise IncompatibleDataError(
                f"Canonical column {column!r} is not compatible with float64."
            ) from error
        result[column] = pd.Series(values, index=dataframe.index, dtype="float64")
    validate_standardized(result, emit_warnings=emit_warnings)
    return result


@dataclass(slots=True)
class CanonicalStreamValidator:
    """Validate canonical fragments as one logical dataset with persistent state.

    Construct once per source, call validate_chunk() in source order, then finish().
    Only the first finite timestamp in the entire stream must be zero; subsequent
    chunks keep their elapsed times. The last finite time survives missing rows
    and chunk boundaries so a local check cannot hide a backwards transition.
    The instance stores scalar state, not all previously validated frames.

    Attributes:
        emit_warnings: Report retained missing values per validated fragment.
    """

    emit_warnings: bool = True
    _rows: int = 0
    _first_finite_time: float | None = None
    _previous_time: float | None = None

    def validate_chunk(self, dataframe: object) -> pd.DataFrame:
        """Copy one canonical fragment to float64 and check it against stream state.

        Pass fragments in original order. Return an independent DataFrame without
        shifting time, sorting or discarding rows. Reject infinity, incompatible
        columns, a nonzero global origin or backwards finite time. Empty fragments
        are permitted; finish() checks that the whole source is nonempty.
        """
        if not isinstance(dataframe, pd.DataFrame):
            raise IncompatibleDataError("Canonical chunks must be pandas DataFrames.")
        columns = tuple(dataframe.columns)
        if columns != CANONICAL_COLUMNS:
            raise IncompatibleDataError(
                f"Canonical chunk columns must be {list(CANONICAL_COLUMNS)!r}."
            )
        result = dataframe.copy(deep=True)
        for column in CANONICAL_COLUMNS:
            try:
                values = np.asarray(numpy_values(dataframe[column]), dtype=np.float64)
            except (TypeError, ValueError) as error:
                raise IncompatibleDataError(
                    f"Canonical column {column!r} is not compatible with float64."
                ) from error
            result[column] = pd.Series(values, index=dataframe.index, dtype="float64")
        arrays = {
            column: cast(
                NDArray[np.float64],
                numpy_values(result[column], dtype=np.float64, copy=False),
            )
            for column in CANONICAL_COLUMNS
        }
        infinite = [
            column for column, values in arrays.items() if np.isinf(values).any()
        ]
        if infinite:
            raise IncompatibleDataError(
                f"Canonical data contains infinity in {', '.join(infinite)}."
            )
        finite = arrays[TIME_COLUMN][np.isfinite(arrays[TIME_COLUMN])]
        if finite.size:
            value = finite[0]
            if self._first_finite_time is None:
                self._first_finite_time = float(value)
                if value != 0.0:
                    raise IncompatibleDataError(
                        "The first finite canonical time must be 0 seconds; "
                        f"received {value!r}."
                    )
            if (self._previous_time is not None and value < self._previous_time) or (
                finite[1:] < finite[:-1]
            ).any():
                raise NonMonotonicTimeError(
                    "Finite canonical time moves backwards across canonical chunks."
                )
            self._previous_time = float(finite[-1])
        self._rows += len(result)
        if self.emit_warnings:
            counts = {
                column: count
                for column in CANONICAL_COLUMNS
                if (count := int(result[column].isna().sum()))
            }
            if counts:
                warnings.warn(MissingValueWarning(counts), stacklevel=2)
        return result

    def finish(self) -> None:
        """Check global nonemptiness and usable time after the iterator is exhausted.

        Call even if no chunks were produced. Raise IncompatibleDataError when the
        source had no rows or no finite timestamp. Do not reuse this instance for a
        different acquisition, because its origin and boundary state are retained.
        """
        if self._rows == 0:
            raise IncompatibleDataError(
                "Canonical datasets must contain at least one row."
            )
        if self._first_finite_time is None:
            raise IncompatibleDataError(
                "Canonical time must contain at least one finite value."
            )
