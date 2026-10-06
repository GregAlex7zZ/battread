# Performance and memory baselines

Measured baselines are provided without throughput targets. Run
`python benchmarks/run.py` from the repository root to reproduce the suite.
Full measurements and the harness are in `benchmarks/`.

## Method

The synthetic dataset has float64 time at one-second intervals, signed current
of -2 mA and voltage of 3.5 V. A capacity variant exercises signed cumulative
reconstruction. Canonical CSV, generic CSV and Parquet inputs contain the same
number of records. Sizes are 100,000 and 1,000,000 rows. Each measured operation
runs in a fresh subprocess; input generation and imports are outside timing.
The OS peak resident-memory counter includes Python, pandas, NumPy and native
Arrow allocations. Input preparation for merge and normalization is outside
timing but included in memory. Three after-change runs are summarized by median
time and maximum peak RAM. The exploratory before-change run has one sample
per case, so improvement ratios are indicative rather than statistical claims.

Local environment: Windows 11 x64, Python 3.14.6, NumPy 2.5.3, pandas 3.0.6,
PyArrow 25.0.1. Synthetic files are cached, small enough to fit in system RAM,
and have few columns. These results do not establish disk-limited throughput,
multi-GB performance, vendor throughput or compatibility across Python versions.

## Timing results

One million rows; streaming chunks contain 10,000 rows.

| Operation | Before, seconds | After median, seconds |
|---|---:|---:|
| Complete CSV read | 4.842 | 2.302 |
| CSV streaming | 4.338 | 2.150 |
| Canonical CSV streaming | 4.161 | 2.154 |
| Parquet streaming | 1.511 | 0.220 |
| Streaming CSV to Parquet | 4.721 | 2.440 |
| Capacity reconstruction and streaming | 8.149 | 6.065 |
| Normalization | 0.233 | 0.006 |
| Merge two one-million-row frames | 0.896 | 0.066 |
| Parquet write | 0.315 | 0.112 |

Recognition remains approximately 1.2 seconds per 10,000 four-column calls.
The measured ingestion cost is chiefly row parsing and numeric conversion,
not recognition, which runs once per source.

## Memory results

Peak RAM in MiB, including roughly 90 MiB of interpreter/library overhead.

| Operation | 100k rows, 10k chunk | 1M rows, 10k chunk | 1M rows, 100k chunk |
|---|---:|---:|---:|
| Generic CSV streaming | 97.1 | 97.4 | 128.0 |
| Canonical CSV streaming | 96.9 | 96.9 | 127.1 |
| CSV to Parquet | 101.4 | 104.7 | 140.6 |
| Reconstruction streaming | 98.0 | 98.3 | 135.7 |
| Parquet streaming | 99.4 | 104.0 | 125.1 |

Complete CSV read peaks at 122.5 MiB for 100k rows and 190.5 MiB for 1M rows.
Merge peaks at 106.8 and 233.1 MiB respectively. These full-result operations
scale with dataset size. CSV streaming scales primarily with chunk size in this
experiment. Arrow decode buffers, Parquet row groups and output metadata also
contribute to RAM, so chunk size is not a strict memory limit.

## Changes and decisions

Repeated per-row time checks and numeric conversions can be costly.
Monotonicity checks now compare finite
NumPy slices, including the previous chunk's final finite time. They preserve
duplicate times, missing rows, the first finite origin and backward-time errors.
Normalization uses one array subtraction. Numeric parsing avoids an intermediate
Arrow-backed string Series, examines only missing numeric positions when counting
malformed cells, and skips redundant multiplication for unit factor one.
Regression tests compare scalar time references and exact CSV/Parquet results
across chunk boundaries.

PyArrow's parsing-only CSV probe took a median 0.325 seconds for 1M rows.
This demonstrates potential, but the probe omits the library's dialect,
malformed-value, clock-time, unit and scientific validation semantics. An Arrow
CSV fast path is deferred until those semantics can be proven equivalent.
Existing Parquet record batches and conversion row groups already stream;
they benefit substantially from vectorized canonical validation. Full pandas
conversion remains necessary at the public API boundary.

The 250,000-row public conversion default remains unchanged. The experiments
show that smaller explicitly selected chunks reduce memory; they do not justify
a universal optimal default. Reconstruction retains its stateful row processing,
which still dominates that path. Multi-file streaming and merge-to-file are
outside the current public API.

Further work: repeated before/after measurements under controlled machine load,
wider and multi-GB fixtures, vendor profiles, reset/NaN-heavy performance cases,
and an equivalent Arrow CSV implementation if measured gains justify it.

## Bounded MPR ingestion comparison (2026-10-06)

`benchmarks/mpr_streaming.py` generates independent synthetic MPR acquisitions
and compares Galvani 0.5.0's original constructor with the adapter's bounded binary
ingestion. Each configuration has three fresh-process repetitions; results are
in `benchmarks/mpr-memory.json`. No private inputs or derived measurements are
included. The scope is **binary ingestion**, not complete scientific normalization
or full-memory pandas read(). Both paths check all encoded current values.

| Synthetic payload | Original median peak RSS | Bounded median peak RSS | Original median peak commit | Bounded median peak commit |
|---|---|---|---|---|
| 32 MiB | 189.6 MiB | 92.2 MiB | 645.5 MiB | 547.8 MiB |
| 128 MiB | 483.3 MiB | 91.6 MiB | 939.8 MiB | 547.2 MiB |

These Windows measurements include interpreter/library/native allocations. The
old path retains module bytes and payload-sized header/record slices; its peak
grows with source size. The bounded path reads small schema metadata and explicit
record batches, without a full-source mapping. Its absolute baseline is not zero,
and committed memory differs substantially from resident RAM on this machine.
The observations demonstrate the eliminated source-copy scaling for these cases,
not a universal memory or throughput guarantee.

The conversion pipeline still uses source-width string rows. MPR reduces its
effective output chunk size for wide schemas; public chunks may be smaller than
requested. Callers collecting frames or using read() still retain full results.
Independent exported fixtures, wire-layout variants and chunk regressions verify
scientific equivalence separately from this memory benchmark.
