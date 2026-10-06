# Large files and memory

## Convert directly to a file

```python
import battread

battread.convert("large.mpr", "standardized.parquet", chunk_size=10_000)
```

This reads, standardizes and writes incrementally. The final destination appears
only after the complete source passes validation. Use `overwrite=True` only when
you intend to replace an existing output. Other reader options, including
`columns={"voltage": "Ewe/V"}`, can be passed to `convert()`.

`read()` collects the complete result into one pandas DataFrame. Use it for
files that fit comfortably in memory. Lowering its internal chunk size does not
remove the memory needed for that final DataFrame.

## Process chunks

```python
for chunk in battread.iter_read("large.csv", chunk_size=10_000):
    print(len(chunk))
```

Consume and release each chunk. Do not collect chunks in a list or concatenate
them unless you intend to hold the complete dataset in memory. Exhaust the
iterator to validate the whole source; when stopping early, close it to release
handles. Scientific state, including time checks and current reconstruction,
continues across chunks.

## What changed for MPR

The reader scans small headers and reads bounded binary records instead of
calling Galvani's full-file constructor. Binary buffers have an 8 MiB ceiling;
wide source tables may yield smaller canonical chunks than requested. Public
outputs still contain the same canonical float64 values and original rows.
Galvani remains an optional schema dependency. Unknown fields and unsupported
layouts fail explicitly; source streaming does not imply universal compatibility.

CSV/TXT, MPT and canonical Parquet also support incremental reading. Neware
binary support is experimental and split NDAX metadata contributes to memory.
Decoder buffers, Python objects and output buffers add overhead: `chunk_size`
is a row-count setting, not a strict RAM budget. See the
[reader guides](../readers/index.md) and [measured baselines](../developer-guide/benchmarks.md).

## Smaller files for repeated use

Canonical Parquet stores only the three standardized columns using a typed,
compressed representation. It usually occupies less disk space than text and
avoids parsing the original vendor container again. Actual size depends on the
data. Conversion does not downsample rows or lower the canonical precision.
The original source can contain additional information absent from the canonical
schema, so retain it according to your own data-retention needs.

## Parallel processing

The library and desktop app do not provide a parallel batch scheduler. Independent
files can be converted in separate processes, each writing its own destination.
Use a shared memory budget and a small worker count; concurrent disk access can
limit or reverse speed gains. Never give two workers the same output path.

Time validation and capacity reconstruction carry state across chunks. Splitting
one source into independently normalized pieces can change scientific results.
Do not parallelize its chunks without a design preserving order and boundary
state. Ordered `merge()` also requires standardized segments and boundary checks.
A benchmark of two independent processes is planned before automatic concurrency
is introduced. Python's [process executor documentation](https://docs.python.org/3/library/concurrent.futures.html#processpoolexecutor)
explains Windows importability and process-start constraints; a pool defined
inside notebook cells is not a portable Windows example.
