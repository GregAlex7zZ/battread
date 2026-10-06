# battread

Convert electrochemical cycling data into a consistent pandas DataFrame.
Python 3.11 or later is required.

```python
import battread

data = battread.read("experiment.csv")
battread.write(data, "standardized.parquet")
```

Every successful read returns exactly three `float64` columns:

| Column | Unit |
|---|---|
| `time_s` | elapsed seconds, starting at zero |
| `current_mA` | milliamperes, preserving measured sign |
| `voltage_V` | volts |

Start with the [example notebook](examples/getting_started.ipynb) or
[usage guide](docs/user-guide/index.md). The notebook uses synthetic data and
starts with reading and saving a file before introducing advanced options.

## Install

From a source checkout:

```bash
python -m pip install .
```

Optional binary readers:

```bash
python -m pip install ".[biologic]"  # Bio-Logic MPR
python -m pip install ".[neware]"    # Experimental Neware NDA/NDAX
```

MPT and Neware CSV exports need no vendor extra. NumPy, pandas and PyArrow are
core dependencies. To run the example notebook, install Jupyter separately
with `python -m pip install jupyterlab` and choose the same Python environment.

## Supported inputs

| Source | Streaming |
|---|---|
| Generic CSV/TXT and canonical text | Yes |
| Canonical Parquet | Yes, using PyArrow batches |
| Bio-Logic MPT | Yes |
| Bio-Logic MPR | Yes, bounded binary reads for supported layouts |
| Neware NDA/NDAX | Experimental; split NDAX retains timestamp metadata |

[Reader guides](docs/readers/index.md) describe format limits. The verified
Neware CSV profile uses **Total Time**, converting clock strings into elapsed
seconds rather than using resetting step time.

## Large files

When you need a converted file, use `convert()` to avoid collecting the complete
result in RAM:

```python
battread.convert("large.mpr", "standardized.parquet", chunk_size=10_000)
```

`iter_read()` yields canonical DataFrames for incremental work. `read()` returns
one complete DataFrame and therefore needs memory for the full result. Keeping
all chunks in a list defeats the memory benefit. The MPR reader now reads small
metadata and bounded binary batches instead of loading the complete acquisition
through Galvani. Chunk size is not a strict total-process RAM limit.

Parquet is recommended for repeated use: it preserves the canonical schema and
usually gives more compact files than text. Streaming lowers RAM use; it does
not alter or downsample measurements. See [large-file guidance](docs/user-guide/large-files.md).

## Scientific choices

Recognition is deterministic and conservative. Use `inspect()` to explain
candidates and `columns` to resolve ambiguity. For example, to explicitly choose
Bio-Logic working-electrode voltage when both voltage labels are present:

```python
data = battread.read("experiment.mpr", columns={"voltage": "Ewe/V"})
```

`Ewe/V` and `<Ewe>/V` are not assumed equivalent. Direct measured current always
wins; established capacity semantics allow reconstruction only when it is absent.
Missing values are retained and warned about. Backward time and unsupported
scientific inference raise errors. `merge()` accepts already-standardized
DataFrames in the order you provide.

The library does not perform cycle, capacity or energy analysis, plotting, or
multi-file streaming merge. See the [API](docs/api/index.md),
[recognition guide](docs/recognition.md), and [future work](TODO.md).

## Development and license

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md).
Copyright (C) 2026 Alessandro Gregucci, for original battread contributions.
Source code is GPL-3.0-or-later: [LICENSE](LICENSE), [authors](AUTHORS.md),
and [third-party notices](THIRD_PARTY_NOTICES.md).
Public fixtures retain their own licenses.

Provided as is, without warranty, subject to the exclusions and liability limits
in sections 15-17 of LICENSE and applicable law. Users must independently verify
converted data before relying on scientific results. Tests do not certify every
instrument or export; no maintenance or support commitment is provided.

Repository: [GregAlex7zZ/battread](https://github.com/GregAlex7zZ/battread).
Report bugs through [GitHub Issues](https://github.com/GregAlex7zZ/battread/issues).
