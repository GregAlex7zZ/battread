# Readers

## Generic CSV and TXT

The generic reader supports comma, semicolon, tab, and whitespace-separated
files. It detects decimal point or decimal comma, UTF-8 and common alternate
encodings, and header presence from a bounded sample. Explicit `sep`, `decimal`,
`encoding`, `header`, and `skiprows` settings take precedence.

The reader streams source records for `iter_read()`. It retains structurally
valid rows with malformed numeric cells as `NaN` and emits standard Python
warnings. Records with the wrong number of fields fail because their scientific
column identity cannot be established safely.

When measured current is absent, the reader supports explicitly declared signed
cumulative or incremental capacity and reliably recognized charge/discharge
capacity pairs. Reconstruction preserves state across chunks and rejects known
resets. See [Current reconstruction](../user-guide/current-reconstruction.md).

See [Reading delimited data](../user-guide/reading-delimited.md) for examples.

## Canonical Parquet

The dedicated Parquet reader accepts exactly the canonical columns in canonical
order. It converts compatible numeric types to `float64`, validates the
existing zero time origin and monotonic time, and streams Arrow record batches
for `iter_read()`. It has no optional backend dependency because PyArrow is a
core dependency.

Canonical CSV and TXT files use the generic reader's canonical fast path. They
retain every row and validate the existing time origin rather than normalizing
it again.

See [Writing and conversion](../user-guide/writing-and-conversion.md) for the
canonical output dialects and conversion workflow.

## Bio-Logic

Bio-Logic MPR uses the optional Galvani binary backend. MPT uses native record
streaming. Both adapters share canonical standardization and conservative
current reconstruction. See [Bio-Logic](biologic.md) for recognized fields,
backend requirements, fixture references, and streaming limitations.

## Neware

NDA and NDAX use a strict streaming adapter with an optional NewareNDA
dependency. See [Neware](neware.md) for supported layouts and timestamp limits.
