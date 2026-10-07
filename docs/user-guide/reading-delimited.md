# Reading delimited data

Elapsed `HH:MM:SS[.fraction]` values support unbounded hours and require seconds
as the time unit. CSVs containing both `Time` and `Total Time` automatically use
`Total Time`, regardless of vendor. Case, whitespace and normalized separators
are ignored (`total_time` and `Total Time` are equivalent labels). Explicit unit
suffixes are preserved; bare paired `Total Time` means seconds. Numeric minutes,
hours or milliseconds are converted according to their declared units.
An unknown or incompatible unit raises an error, rather than becoming seconds.

Explicit mappings take precedence, for example
`read(path, columns={"time": "Time(s)"})` to select the other clock.
Invalid minute/second fields are retained as NaN with warnings.

`read()` loads a complete CSV or TXT source and returns a pandas DataFrame with
exactly `time_s`, `current_mA`, and `voltage_V` as `float64`. The generic reader
detects common delimiters, decimal separators, encodings, headers, scientific
columns, and units.

```python
from battread import read

data = read("experiment.csv")
```

Use `inspect()` to review the detected text structure and the evidence for each
column without converting the complete file.

```python
from battread import inspect

information = inspect("experiment.csv")
print(information.delimiter)
for match in information.columns:
    print(match.source_position, match.source_column, match.state, match.evidence)
```

When the structure is unusual, provide parser and scientific overrides. An
integer `header` counts nonblank table records after `skiprows`; `skiprows`
itself counts physical lines, including blank lines.

```python
data = read(
    "instrument-export.txt",
    sep=";",
    decimal=",",
    encoding="cp1252",
    skiprows=3,
    header=0,
    columns={"time": 0, "current": 2, "voltage": 4},
    units={"time": "s", "current": "A", "voltage": "mV"},
)
```

Set `header=None` for a headerless file. Positional mappings preserve the first
data row and distinguish duplicate column names. With `autodetect=False`, all
three required mappings and units must be explicit.

## Large files

`iter_read()` parses the source incrementally and yields canonical pandas
chunks. The time origin belongs to the complete source, so later chunks do not
restart at zero. Exhaust the iterator to complete whole-source checks.

```python
from battread import iter_read

for chunk in iter_read("large-export.csv", chunk_size=100_000):
    process(chunk)
```

An individual chunk is a fragment of one logical dataset and may begin after
zero or contain only missing time. Such a chunk is not an independent input to
`merge()`.

## Malformed values and rows

A nonempty malformed numeric cell is retained as `NaN` with a
`MalformedValueWarning`; final missing values also produce a
`MissingValueWarning`. A row with too few or too many fields raises
`CorruptedFileError`, because the reader cannot preserve its column identity
safely. Rows are never skipped automatically.

Duplicate candidate measurements and other scientific ambiguities remain
inspectable, while `read()` requires an explicit column mapping before it can
standardize them.


## Remaining ambiguities

Two `Total Time` columns still require a positional choice. A third distinct
measured clock is not suppressed by the paired-clock preference. Other duplicate
current or voltage candidates also raise `AmbiguousColumnError`.

```python
information = inspect("experiment.csv")
# Positions are zero-based and distinguish duplicate labels.
data = read("experiment.csv", columns={"current": 2}, units={"current": "mA"})
```

This preference belongs to the CSV reader, not to global fuzzy recognition.
Generic TXT files keep conservative selection; verified vendor profiles may
establish their own time semantics. `autodetect=False` still requires explicit
mappings and units. Standardized output retains missing rows, direct current
sign, time order and scientifically equivalent chunked results.

The separate [desktop GUI](https://github.com/GregAlex7zZ/battread-gui) can ask for
an explicit column and unit when ambiguity occurs, then resume its worker. The
library itself never opens a dialog; its public mapping API is unchanged.
