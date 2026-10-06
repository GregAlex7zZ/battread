# Bio-Logic

`read()`, `inspect()`, `iter_read()`, and `convert()` support Bio-Logic `.mpr`
binary acquisitions and EC-Lab/BT-Lab `.mpt` ASCII exports. Detection uses file
magic; column names and scientific overrides remain visible through
`inspect()`.

```python
from battread import read, convert

data = read("experiment.mpr")
convert("experiment.mpt", "standardized.parquet")
```

## Installation and backend

Binary MPR support requires the optional Galvani extra:

```sh
pip install "battread[biologic]"
```

The tested backend is Galvani 0.5.0 (`>=0.5.0,<0.6`), licensed GPL-3.0-or-later.
Its schema functions and import remain inside the adapter. The full-memory
MPRfile constructor is not used. Generic reads and canonical
output consumption do not require Galvani. MPT uses battread's native text
path and works without the optional extra.

## Recognized measurements

Supported vendor fields include `time/s`, `I/mA`, `<I>/mA`, `Ewe/V`,
`<Ewe>/V`, `<Ewe/V>`, and `Ecell/V`. Competing measured currents or voltages
require an explicit mapping. Galvani's duplicate-field suffixes also remain
scientifically ambiguous. Direct current retains its sign and missing values.
AC magnitude fields such as `|I|/A` do not automatically supply signed cycling
current.

When direct current is absent, Bio-Logic `dq/mA.h`, `dQ/mA.h`, or `dQ/C`
is the preferred source. The adapter recognizes these verified vendor fields
as signed interval charge aligned with the preceding interval:
`current_mA[i] = 3600 * dq_mAh[i] / (time_s[i] - time_s[i-1])`.
The first current is missing. No caller declaration is required for these
known fields; `inspect()` reports their semantics and alignment.

An absent direct current and absent `dq` can be reconstructed from the separately labelled
`Q charge/mA.h` and `Q discharge/mA.h` fields when both remain non-decreasing.
Known decreases cause failure. The fixture's real capacity resets are tested.

Competing `dq` candidates require an explicit column selection. Explicit
capacity mappings and semantic/alignment overrides remain authoritative.
Selected `dq` with no finite reconstructable current causes an error; it is
not silently replaced with another capacity strategy. A present measured-current
column containing missing values is retained rather than replaced by `dq`.

`(Q-Qo)` fields remain inspectable capacity candidates requiring explicit
declarations of their semantics. Generic CSV/TXT `dq` labels still do not
establish signedness or alignment. See
[Current reconstruction](../user-guide/current-reconstruction.md).

## Text parsing

MPT uses its declared header-line count and tab delimiter. Decimal point and
comma and common text encodings are supported; explicit `decimal` and
`encoding` settings take precedence. The optional terminal tab in an EC-Lab
header or data record is structural padding. All scientific cells retain their
column identity. Missing or malformed numeric cells remain missing with
standard warnings; incorrect field counts fail.

`sep`, `header`, and `skiprows` cannot replace the declared MPT structure.
MPR rejects text-parser options. Both formats accept scientific column and unit
overrides through the ordinary API.

## Streaming and limitations

| Source | Source streaming | Chunk behavior |
|---|---|---|
| MPT | Yes | Reads records incrementally, preserving reconstruction state |
| MPR | Yes | Bounded binary batches feed the existing scientific conversion pipeline |

MPR inspection reads small metadata prefixes and seeks over the measurement
payload. The supported data versions are 0 (legacy and paired-ID encodings), 2
and 3, with either Galvani module header format. Binary batch buffers are capped
at 8 MiB; wide source schemas can yield smaller chunks than requested to limit
string-row buffers. `read()` still collects the complete canonical result in RAM;
use `iter_read()` or `convert()` for large acquisitions.

Iterators release the source on exhaustion, error or explicit `close()`. Sources
must remain unchanged during processing; detected replacement/truncation/mutation
raises an error. The buffer ceiling is not a strict total-process RAM limit.
Unsupported Galvani column IDs (including unverified ID 215) raise
`UnsupportedFormatError`; corrupted or truncated acquisitions raise
`CorruptedFileError`. No binary format coverage beyond the tested Galvani
schemas is promised. Capacity resets are never repaired or unwrapped.

See [ADR 0006](../adr/0006-memory-bounded-mpr-ingestion.md) and the
[synthetic memory comparison](../developer-guide/benchmarks.md).

Acceptance tests use an unchanged, attributed MPR/MPT pair and an independent
BT-Lab ASCII reference. See [fixture provenance](https://github.com/echemdata/galvani/tree/d4a5f444b16eae57d2edfad6df774ead95c92fd6/tests/testdata).
