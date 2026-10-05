# Canonical data

A complete standardized dataset is a pandas DataFrame with exactly these
ordered columns and dtypes:

| Column | dtype | Unit |
|---|---|---|
| time_s | float64 | seconds |
| current_mA | float64 | milliamperes |
| voltage_V | float64 | volts |

The DataFrame must contain at least one row and one finite time. Its first
finite time must be zero, finite time must never decrease, and no canonical
column may contain infinity. Missing values remain in place and produce
**MissingValueWarning** during validating operations.

The is_standardized() function applies this contract without warnings or
mutation:

    from battread import is_standardized

    if is_standardized(dataframe):
        ...

## Sequential merge

The merge() function accepts already-standardized DataFrames in caller-supplied
order. It keeps each segment's internal intervals and shifts each later segment
after the preceding segment.

    from battread import merge

    combined = merge([first, second, third])

The bridge interval is the last positive interval between adjacent finite rows
of the preceding segment. If none exists, the first such interval in the next
segment is used. Missing rows are never crossed to infer an interval. The merge
fails when neither neighboring segment provides a safe bridge.
