# Benchmarks

Run from the project root with the project interpreter:

```powershell
.\.venv\Scripts\python.exe benchmarks/run.py --repeat 3 --output benchmarks/results.json
```

The harness generates 100,000- and 1,000,000-row synthetic datasets, then runs
each operation in a fresh subprocess. It measures CSV reading, canonical CSV
and Parquet streaming, normalization, recognition, capacity reconstruction,
merge, Parquet writing and streaming conversion. Chunk sizes default to 10,000
and 100,000. No speed thresholds are enforced.

Use `--sizes`, `--chunks`, `--repeat` and `--cases` to narrow an experiment.
For example, `--cases arrow_csv_probe --sizes 1000000 --chunks 10000` measures
Arrow parsing alone; it does **not** perform scientific standardization and is
not directly comparable to the validated library reader.

The JSON records elapsed wall time, throughput, OS lifetime peak resident RAM,
pre-operation peak RAM, repetitions and dependency/platform versions. Windows
uses PeakWorkingSetSize; Unix uses ru_maxrss. RAM includes native allocations
and interpreter imports. It is not Python-only tracemalloc memory. Input
generation and imports are outside the timed region. Merge and normalization
inputs are prepared before timing, but remain included in process peak RAM.
Recognition uses 10,000 calls and its throughput unit is calls per second.
Merge outputs twice the input row count. The read chunk argument in result
records labels the experimental configuration; `read()` uses its internal
250,000-row ingestion default.

Retained measurements:

- `baseline-before.json`: one exploratory measurement per configuration.
- `baseline-after.json`: three measurements per configuration after optimization.
- `arrow-probe.json`: three parsing-only measurements.

See `docs/developer-guide/benchmarks.md` for results, limitations and decisions.
These are local baselines, not universal performance guarantees. Further
experiments should repeat both comparison versions and control machine load.

MPR ingestion has a separate synthetic-only harness:

```powershell
.\.venv\Scripts\python.exe benchmarks/mpr_streaming.py --output benchmarks/mpr-memory.json
```

It compares Galvani's original constructor with bounded binary batches in fresh
processes, including Windows peak committed memory and resident RAM. This scope
does not benchmark complete scientific standardization. See the developer
benchmark guide and ADR 0006 for results and interpretation.
