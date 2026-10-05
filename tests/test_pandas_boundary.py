# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regressions for the typed pandas boundary used by scientific conversion.

The boundary must preserve raw values during export and retain original row
positions and measured signs during numeric coercion. The interpreter matrix
also checks that postponed pandas generic annotations remain importable.
"""

import numpy as np
import pandas as pd

from battread._pandas import numeric_values, numpy_values


def test_export_preserves_unconverted_values_and_source_order() -> None:
    """Keep strings and missing objects untouched until scientific coercion.

    Nonsequential labels must not reorder rows; exporting is not recognition,
    sorting or missing-value repair. Raw object storage must remain distinct
    from the float64 conversion performed later by the canonical core.
    """
    values = pd.Series(["-2", None, "invalid"], index=[8, 2, 5], dtype=object)
    result = numpy_values(values)
    assert result.dtype == np.dtype(object)
    assert result.tolist() == ["-2", None, "invalid"]
    assert values.index.tolist() == [8, 2, 5]


def test_numeric_coercion_retains_missing_positions_and_current_sign() -> None:
    """Malformed and empty source cells become float64 NaNs without losing rows.

    The surrounding reader reports these cells separately; the type boundary
    must preserve their positions so chunk processing and warning counts can
    remain equivalent to the original parser.
    """
    values = pd.Series(["-2.5", "invalid", "", None, "0", "1.25"], dtype=object)
    result = numeric_values(values)
    assert result.dtype == np.dtype("float64")
    np.testing.assert_array_equal(result, [-2.5, np.nan, np.nan, np.nan, 0, 1.25])
