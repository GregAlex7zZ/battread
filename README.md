# battread

Vendor-independent standardization of electrochemical cycling data.

Repository: [GregAlex7zZ/battread](https://github.com/GregAlex7zZ/battread).
Bug reports: [GitHub Issues](https://github.com/GregAlex7zZ/battread/issues).

Version 0.1.0 is prepared for publication. Remote GitHub settings and GitHub Actions
verification remain pending; see [RELEASE_STATUS.md](RELEASE_STATUS.md).
The Windows/Linux Python 3.11-3.14 and minimum-dependency matrix has passed;
see [compatibility results](docs/testing/PYTHON_COMPATIBILITY.md), including
the final release checks.

**Author and maintainer:** Alessandro Gregucci.
Copyright (C) 2026 Alessandro Gregucci, for original project contributions;
see [COPYRIGHT.md](COPYRIGHT.md).

This project was developed with substantial assistance from OpenAI Codex.
Alessandro defined the requirements and scientific decisions; Codex generated
and revised implementation code, tests, notebooks and documentation, and ran
automated checks. See [AUTHORS.md](AUTHORS.md) for the contribution statement.

Every successful read returns a pandas DataFrame with exactly these columns:

| Column | Unit | dtype |
|---|---|---|
| `time_s` | elapsed seconds, starting at the first finite time | float64 |
| `current_mA` | milliamperes, preserving measured sign | float64 |
| `voltage_V` | volts | float64 |

## Installation

Python 3.11 or later is required. Install from a source checkout:

```bash
python -m pip install .
python -m pip install ".[biologic]"
python -m pip install ".[neware]"
python -m pip install ".[all]"
```

Core dependencies are NumPy, pandas and PyArrow. Galvani is optional for Bio-Logic
MPR; native MPT reading needs no vendor extra. NewareNDA is optional for NDA/NDAX.
Neware CSV exports use the generic reader without vendor dependencies.
Dependencies and licenses are recorded in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

### Third-party acknowledgements

Bio-Logic MPR decoding relies on [Galvani](https://github.com/echemdata/galvani),
by Chris Kerr and contributors (GPL-3.0-or-later). Experimental Neware binary
decoding relies on [NewareNDA](https://github.com/d-cogswell/NewareNDA), by Daniel
Cogswell and contributors (BSD-3-Clause, copyright SES AI Corporation).
The Neware adapter also contains adapted record layouts; their original
copyright, license conditions and disclaimer are retained in
[the NewareNDA license](licenses/NewareNDA-BSD-3-Clause.txt).
These acknowledgements do not imply endorsement by the upstream projects.

## Read and inspect

```python
from battread import read, inspect

data = read("experiment.mpr")
information = inspect("experiment.csv")
for match in information.columns:
    print(match.source_column, match.state, match.unit, match.evidence)
```

Recognition uses deterministic labels, aliases, units, vendor hints and negative
evidence. It never uses fuzzy matching for scientific decisions. Ambiguity raises
an error; `inspect()` explains candidates without requiring successful conversion.

For unusual exports, specify source columns, units and parser structure:

```python
data = read(
    "export.txt",
    columns={"time": "Elapsed", "current": "Measured I", "voltage": "Cell E"},
    units={"time": "min", "current": "A", "voltage": "mV"},
    sep=";", decimal=",", encoding="utf-8", skiprows=2, header=0,
)
```

Column mappings accept names or zero-based positions. Duplicate names require
positions. `autodetect=False` disables semantic inference; unspecified text
structure can still be detected. `header=None` means headerless. `skiprows`
counts physical lines and integer `header` counts nonblank table records after
that prefix. See [the delimited guide](docs/user-guide/reading-delimited.md).

The verified Neware CSV header profile automatically selects **Total Time**
instead of resetting **Time**. `HH:MM:SS[.fraction]` becomes elapsed float64
seconds starting at zero. Other export variants can use
`columns={"time": "Total Time"}, units={"time": "s"}` explicitly.

## Large files and canonical output

```python
from battread import convert, iter_read, write

for chunk in iter_read("large.csv", chunk_size=10_000):
    print(len(chunk))

convert("large.csv", "standardized.parquet", chunk_size=10_000)
write(data, "standardized.csv")
```

`read()` returns one complete DataFrame; `iter_read()` yields canonical
DataFrames. `convert()` publishes its destination only after whole-source
validation succeeds. Existing destinations require `overwrite=True`. Failures
preserve an existing destination and remove the operation's temporary output.
Parquet is recommended for large datasets. CSV output uses UTF-8, commas and a
decimal point; TXT uses tabs. Both have a header and omit the index. The library
reads all its own outputs and validates their existing zero origin.

| Source | Implementation | Streaming |
|---|---|---|
| Generic CSV/TXT, including canonical text | Native delimited reader | Yes |
| Canonical Parquet | PyArrow batches | Yes; decoder buffers also contribute to RAM |
| Bio-Logic MPT | Native text adapter | Yes |
| Bio-Logic MPR | Galvani 0.5.x schemas | Bounded binary reads and canonical chunks |
| Neware NDA | Strict NewareNDA record adapter | Yes, supported layouts |
| Neware NDAX | Strict full/split NDC adapter | Yes; split timestamp metadata is retained |

See [Bio-Logic](docs/readers/biologic.md), [Neware](docs/readers/neware.md) and
[benchmarks](docs/developer-guide/benchmarks.md) for limitations and measured RAM.
Chunk size controls a major part of memory use, but is not a strict RAM limit.

The current Neware workflow targets CSV autoexports. NDA/NDAX adapters are
experimental: real-fixture coverage is limited and some layouts have only
synthetic tests. Broader instrument/export validation is planned for future
versions in [the maintenance checklist](TODO.md).

## Current reconstruction and merge

Direct measured current always takes precedence, even when it is missing in
some or all rows. Bio-Logic's verified signed `dq` is preferred only when direct
current is absent. Generic capacity requires established semantics; an alias
or capacity unit alone cannot establish them.

```python
data = read(
    "capacity.csv", columns={"capacity": "Increment (mAh)"},
    capacity_kind="delta_signed", capacity_interval="previous",
)
```

Supported strategies are signed cumulative capacity, signed incremental capacity
with declared previous/next alignment, and verified charge/discharge capacity
pairs. Endpoints or invalid intervals remain NaN with warnings when safe.
Known resets fail; the library does not infer cycles or unwrap capacity resets.
See [current reconstruction](docs/user-guide/current-reconstruction.md).

```python
from battread import merge

combined = merge([read("part1.csv"), read("part2.csv")])
```

`merge()` accepts standardized DataFrames in caller order. It bridges each pair
using the preceding last positive adjacent interval, falling back to the next
segment's first positive adjacent interval. Missing rows never provide an
interval across a gap. See [canonical data](docs/user-guide/canonical-data.md).

## Scientific boundaries

### No warranty and scientific verification

This software is provided **as is, without warranty**, to the extent permitted
by applicable law. No guarantee is made about accuracy, completeness, fitness
for a particular purpose or suitability for a particular instrument or export.
Users are responsible for independently checking converted data against their
source records before relying on it in research, publications or decisions.
Passing tests does not certify every acquisition or downstream conclusion.

The exclusions of warranty and limitations of liability in sections 15-17 of
[LICENSE](LICENSE) apply. Authors, copyright holders and contributors accept no
liability for erroneous results, data loss or resulting damages except where
required by applicable law or expressly agreed in writing. No support,
maintenance or response-time commitment is provided.

Missing rows are retained and reported using Python warnings. Malformed numeric
cells in structurally valid rows become warned NaN; structurally malformed rows
fail. Backward time, canonical infinity and unsupported inference fail explicitly.
All domain exceptions derive from `battread.exceptions.DataStandardizationError`.

The public functions are `read`, `iter_read`, `inspect`, `detect_format`, `merge`,
`write`, `convert` and `is_standardized`. The library does not perform cycle,
half-cycle, capacity or energy analysis, plotting, Excel output or multi-file
streaming merge. See [the API](docs/api/index.md) and
[technical specification](docs/specification/TECHNICAL_SPECIFICATION.md).

## Development and license

```bash
python -m pip install -e ".[dev,docs,all]"
pytest
ruff check .
ruff format --check .
python -m pyright --pythonpath "$(python -c 'import sys; print(sys.executable)')"
mkdocs build --strict
python -m build
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md), and
[the acceptance report](docs/testing/V0_1_ACCEPTANCE_REPORT.md).
Source code is GPL-3.0-or-later; see [LICENSE](LICENSE). Third-party test fixtures
retain their own licenses and attribution. Only documented, redistributable
fixtures and synthetic data belong in the public repository.
