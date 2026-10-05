# Writing and conversion

`write()` validates one complete canonical pandas DataFrame and writes Parquet,
CSV, or TXT. The input must contain exactly `time_s`, `current_mA`, and
`voltage_V` in that order. Compatible numeric values are converted to
`float64`, but writing never shifts time, reorders columns, drops extra
columns, or removes rows.

```python
from battread import write

path = write(data, "standardized.parquet")
```

The output format is inferred from the destination suffix. Pass `format` when
the filename does not identify the desired representation.

```python
write(data, "result.data", format="parquet")
```

CSV output is UTF-8 with comma-separated fields. TXT output is UTF-8 with
tab-separated fields. Both include the canonical header, use a decimal point,
and omit the pandas index. Parquet preserves the three-column schema and is the
recommended format for large datasets.

## Streaming conversion

`convert()` reads and validates a source incrementally and writes canonical
chunks directly to the destination format. This avoids assembling a second
complete output DataFrame when the selected reader supports streaming.

```python
from battread import convert

convert(
    "large-export.csv",
    "standardized.parquet",
    chunk_size=100_000,
)
```

Reader options accepted by `iter_read()`, including explicit column and unit
mappings for generic text, are also accepted by `convert()`.

## Publication and overwrite behavior

Writers first create a temporary file in the destination directory. The final
path appears only after the complete DataFrame or source iterator passes
validation and the writer closes successfully. A failed conversion removes its
temporary file and leaves any existing destination unchanged.

Existing destinations raise `OutputExistsError` unless `overwrite=True` is
passed. The same check is enforced when another process creates the destination
while a conversion is running.

## Reading canonical outputs

All three output formats can be passed back to `read()` or `iter_read()`.
Canonical sources are already normalized, so their first finite time must be
zero. A nonzero origin raises an error rather than being silently repaired.
