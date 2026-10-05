# Architecture & Public API Specification
## Version 0.1

**Status:** Draft  
**Specification version:** 0.1  
**Related document:** Data Standardization Library — Technical Specification v0.1  
**Target language:** Python  
**Minimum Python version:** Python 3.11  
**Public tabular interface:** pandas  
**Primary columnar backend:** PyArrow  
**Recommended interchange format:** Apache Parquet

---

# 1. Purpose

This document defines the architecture and intended public API of the Data Standardization Library.

The Technical Specification defines **what the library must do**.

This document defines:

- how the software is organized;
- how readers interact with the core;
- how automatic recognition is represented;
- how users interact with the package;
- how large files are processed;
- how optional vendor dependencies are isolated;
- how errors and warnings are exposed;
- how future readers can be added.

Implementation details MAY evolve as long as the externally observable behavior remains compliant with the Technical Specification.

---

# 2. Architectural goals

The architecture SHALL optimize for:

1. modularity;
2. scientific correctness;
3. extensibility;
4. transparent automatic recognition;
5. low coupling between vendor readers;
6. efficient processing of large datasets;
7. simple public APIs;
8. testability;
9. maintainability by external contributors;
10. clean dependency and licensing boundaries.

---

# 3. High-level architecture

The library shall conceptually consist of the following layers:

```text
                 PUBLIC API
                     │
        ┌────────────┼────────────┐
        │            │            │
      read()      convert()     merge()
        │            │            │
        └────────────┼────────────┘
                     │
                ORCHESTRATION
                     │
        ┌────────────┼─────────────┐
        │            │             │
      FORMAT      COLUMN         UNIT
     DETECTION   RECOGNITION   RECOGNITION
        │            │             │
        └────────────┼─────────────┘
                     │
                   READERS
              ┌──────┼──────┐
              │      │      │
          BioLogic Neware Delimited
              │      │      │
              └──────┼──────┘
                     │
                NORMALIZATION
                     │
                     ▼
          ┌────────────────────┐
          │ time_s             │
          │ current_mA         │
          │ voltage_V          │
          └────────────────────┘
                     │
              VALIDATION / MERGE
                     │
                   EXPORT
```

---

# 4. Package structure

A recommended initial source tree is:

```text
src/
└── battread/
    ├── __init__.py
    ├── api.py
    │
    ├── readers/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── registry.py
    │   ├── biologic.py
    │   ├── neware.py
    │   ├── delimited.py
    │   └── standardized.py
    │
    ├── recognition/
    │   ├── __init__.py
    │   ├── columns.py
    │   ├── aliases.py
    │   ├── capacity.py
    │   ├── units.py
    │   ├── scoring.py
    │   └── models.py
    │
    ├── normalization/
    │   ├── __init__.py
    │   ├── time.py
    │   ├── current.py
    │   └── voltage.py
    │
    ├── reconstruction/
    │   ├── __init__.py
    │   └── current.py
    │
    ├── merge.py
    ├── validation.py
    ├── conversion.py
    ├── exporters.py
    ├── warnings.py
    ├── exceptions.py
    ├── constants.py
    └── typing.py
```

Exact filenames MAY change.

Separation of responsibilities SHALL remain.

---

# 5. Public API surface

Primary user-facing functions SHOULD be importable directly from the top-level package.

Expected usage:

```python
from battread import (
    read,
    iter_read,
    inspect,
    detect_format,
    merge,
    convert,
    write,
    is_standardized,
)
```

Users SHALL NOT need to import internal reader implementations for normal operation.

---

# 6. Path handling

Public file APIs SHALL accept:

```python
str
pathlib.Path
os.PathLike
```

Example:

```python
read("experiment.mpr")
```

and:

```python
from pathlib import Path

read(Path("experiment.mpr"))
```

File-like objects MAY be introduced later.

Version 0.1 primarily targets filesystem paths.

---

# 7. `read()`

`read()` is the main convenience API for loading one complete logical dataset into memory.

Reference v0.1 signature (the keyword names and defaults are part of the contract):

```python
def read(
    path,
    *,
    reader=None,
    columns=None,
    units=None,
    capacity_kind=None,
    capacity_interval=None,
    autodetect=True,
    sep=None,
    decimal=None,
    encoding=None,
    header="infer",
    skiprows=0,
) -> pandas.DataFrame:
    ...
```

Implementation SHALL provide complete type annotations. `columns` maps semantic
keys to source names or zero-based positions; supported keys are `time`,
`current`, `voltage`, `capacity`, `charge_capacity`, and `discharge_capacity`.
`units` uses the same semantic keys and supported unit strings.

### 7.1 Capacity overrides

`capacity_kind` accepts `None`, `"cumulative_signed"`, or `"delta_signed"`.
A non-`None` value requires an explicit `columns["capacity"]` mapping and
overrides the inferred semantics of that selected column. It does not override
usable measured current, dimensional compatibility, or known reset evidence.
Separate charge/discharge capacities use their own mapping keys.

`capacity_interval` accepts `None`, `"previous"`, or `"next"` and applies only
to signed incremental capacity:

| Value | Meaning of source `dQ[i]` | Output current | Unavailable endpoint |
|---|---|---|---|
| `previous` | Charge transferred over `(t[i-1], t[i]]` | `I[i] = 3600 * dQ[i] / (t[i] - t[i-1])` | First row |
| `next` | Charge transferred over `[t[i], t[i+1])` | `I[i] = 3600 * dQ[i] / (t[i+1] - t[i])` | Last row |

Capacity in these formulas is converted to `mAh` and time to seconds first.
An explicit interval overrides reader-provided alignment. If neither supplies
alignment, incremental reconstruction raises `CurrentReconstructionError`.
When cumulative reconstruction is selected, a non-`None` interval option raises
`CurrentReconstructionError`; cumulative differentiation always uses the previous
adjacent row. No option enables generic reset repair.

### 7.2 Generic text parsing controls

The following options apply to delimited text, including canonical CSV/TXT.
Explicit values override inspection and SHALL be shared by `read()`,
`iter_read()`, `inspect()`, and the source side of `convert()`.

| Option | Default | v0.1 meaning |
|---|---|---|
| `sep` | `None` | Detect the delimiter; explicit values are one character or `"whitespace"` for runs of spaces/tabs. General regular expressions are unsupported. |
| `decimal` | `None` | Detect `"."` or `","`; an explicit value selects one of these decimal separators. |
| `encoding` | `None` | Detect a supported text encoding; an explicit codec name uses strict decoding. No replacement of undecodable bytes. |
| `header` | `"infer"` | Detect header presence; `None` means headerless, and a non-negative integer identifies the header record after the skipped prefix. |
| `skiprows` | `0` | Explicitly skip this many physical lines at the start, including blank lines; lists and callables are unsupported. |

For an integer `header`, count nonblank table records from zero after `skiprows`.
Records before the selected header are excluded only because the user requested
that header position. Blank structural lines are not scientific data rows.
Sampling SHALL restart from the beginning with these same options.
Uncertain structure SHALL raise `IncompatibleDataError` with the relevant
override suggestion rather than guess or lose the first data row.
Numeric malformed cells may be retained as `NaN` with a warning if row/column
identity remains safe; structurally uninterpretable records fail with
`CorruptedFileError`. Automatic row skipping is unsupported.

Passing a non-default text option to a reader that does not support it raises
`IncompatibleDataError` rather than silently ignoring it. Invalid option values
also raise `IncompatibleDataError`. Duplicate source names require positional
mapping; a name matching more than one position raises `AmbiguousColumnError`.

Example:

```python
read(
    "export.txt",
    sep=";",
    decimal=",",
    encoding="cp1252",
    skiprows=3,
    header=0,
    columns={"time": "Time", "current": "Current", "voltage": "Voltage"},
    units={"time": "s", "current": "mA", "voltage": "V"},
)
```

---

# 8. `read()` behavior

`read()` SHALL:

1. detect or validate the file format;
2. select the appropriate reader;
3. inspect relevant columns;
4. apply explicit mappings where provided;
5. recognize missing mappings automatically where enabled;
6. determine units;
7. obtain time;
8. obtain voltage;
9. obtain current or safely reconstruct it;
10. normalize units;
11. normalize elapsed time to zero;
12. convert canonical columns to `float64`;
13. validate the result;
14. return a canonical pandas DataFrame.

Returned columns SHALL be:

```text
time_s
current_mA
voltage_V
```

---

# 9. Partial explicit mapping

Explicit mappings MAY be partial.

Example:

```python
df = read(
    "experiment.csv",
    columns={
        "current": "Cell Current",
    },
)
```

The library SHALL use the explicit current mapping while continuing automatic recognition for time and voltage.

The same principle applies to unit overrides.

---

# 10. Autodetection control

Automatic recognition SHALL be enabled by default.

An advanced user MAY disable it.

Conceptually:

```python
read(
    "experiment.csv",
    columns={
        "time": 0,
        "current": 1,
        "voltage": 2,
    },
    units={
        "time": "s",
        "current": "mA",
        "voltage": "V",
    },
    autodetect=False,
)
```

When autodetection is disabled, all required unresolved information MUST be supplied explicitly.

`autodetect` controls semantic column and unit recognition. It does not disable
format routing or detection of unspecified text parsing options. Explicit
column, unit, and parsing overrides always take precedence.

---

# 11. Reader override

Users MAY explicitly select a reader.

Example:

```python
read(
    "experiment.dat",
    reader="biologic",
)
```

An explicit reader selection SHALL override ordinary automatic format selection.

The selected reader SHALL still validate that the source is compatible where practical.

---

# 12. `inspect()`

`inspect()` SHALL provide source interpretation information without performing unnecessary complete conversion.

Conceptually:

```python
info = inspect("experiment.csv")
```

Its purpose is:

- debugging;
- transparency;
- GUI previews;
- examining ambiguous files;
- understanding automatic recognition.

`inspect(path, **read_options)` accepts the same interpretation options as
`read()`. It returns ambiguous and unresolved recognition states for review;
these states alone do not raise `AmbiguousColumnError` or `MissingColumnError`.
Invalid explicit options, unreadable input, or unsafe parsing still raise the
appropriate exception. A successful bounded inspection is not a guarantee that
the complete file will pass validation.

---

# 13. Inspection result

`inspect()` SHOULD return an immutable structured object.

Conceptually:

```python
@dataclass(frozen=True)
class InspectionResult:
    format: str
    reader: str
    columns: tuple[ColumnMatch, ...]
    delimiter: str | None
    decimal_separator: str | None
    encoding: str | None
    current_reconstruction_required: bool | None
```

Exact fields MAY vary by source type.

`current_reconstruction_required` is `None` when unresolved or ambiguous
recognition prevents deciding the current strategy. Inspection SHALL expose
recognition states and source positions, including duplicate labels, and any
known capacity interval alignment. Inspection represents the sampled source;
it SHALL NOT claim that later rows were validated.

Inspection information SHALL NOT be embedded into the standardized DataFrame.

---

# 14. Inspection of large files

Where possible, `inspect()` SHALL operate on a bounded sample rather than the entire source.

For generic text formats, it SHOULD inspect enough data to determine:

- likely encoding;
- delimiter;
- decimal separator;
- header;
- candidate columns;
- units;
- representative numerical behavior where required.

Inspection MUST NOT change subsequent reading behavior by consuming or omitting data.

---

# 15. Rejected candidates

Inspection MAY expose discarded recognition candidates.

Example conceptual output:

```text
Selected current:
    Cell Current (mA)

Rejected candidates:
    Current Range
    Current Limit
```

This is recommended for debugging and GUI inspection but does not need to be part of the basic `read()` interface.

---

# 16. `detect_format()`

A public or semi-public format detection function SHOULD exist.

Conceptually:

```python
format_info = detect_format("experiment.mpr")
```

Detection SHALL use content-based evidence where available.

Filename extensions SHALL be treated as useful evidence but not absolute truth.

A recognized file signature MAY override an incorrect extension.

---

# 17. Reader abstraction

Readers SHALL implement a common interface.

A class-based reader architecture is required.

Conceptually:

```python
class BaseReader:
    name: str

    def can_read(self, source) -> bool:
        ...

    def inspect(self, source, **options):
        ...

    def read(self, source, **options):
        ...

    def iter_read(self, source, **options):
        ...
```

Not every reader is required to support true `iter_read()`.

Capabilities SHALL be declared explicitly.

---

# 18. Reader capabilities

Reader capabilities SHOULD be represented through an immutable structure.

Conceptually:

```python
@dataclass(frozen=True)
class ReaderCapabilities:
    streaming: bool
    inspection_without_full_read: bool
    supports_column_mapping: bool
    supports_unit_mapping: bool
```

This information MAY later be surfaced in documentation or GUI interfaces.

---

# 19. Reader registry

Readers SHALL be registered centrally.

Conceptually:

```python
READERS = [
    StandardizedReader(),
    BioLogicReader(),
    NewareReader(),
    DelimitedReader(),
]
```

The public `read()` function SHALL NOT contain large conditional blocks such as:

```python
if suffix == ".mpr":
    ...
elif suffix == ".nda":
    ...
```

Reader selection SHALL be delegated to the registry.

---

# 20. Reader detection priority

Highly specific readers SHALL take precedence over generic readers.

For example:

```text
Standardized Parquet
Bio-Logic
Neware
Generic delimited text
```

A generic `.txt` reader MUST NOT accidentally claim a file recognized more confidently by a specialized reader.

---

# 21. Future external readers

The internal reader interface SHOULD be designed so that future third-party readers can eventually be registered from separate packages.

Plugin discovery does not need to be implemented in v0.1.

The architecture SHALL avoid assumptions that make external readers impossible later.

---

# 22. Recognition result model

Recognition results SHOULD use immutable typed structures.

Conceptually:

```python
@dataclass(frozen=True)
class ColumnMatch:
    source_column: str | int
    source_position: int
    quantity: str
    unit: str | None
    semantic: str | None
    interval_alignment: str | None
    state: str
    confidence: float
    evidence: tuple[str, ...]
```

Confidence values SHALL primarily be an internal implementation mechanism.

Public behavior SHALL rely on resolved, ambiguous, or unresolved states rather than exposing arbitrary numeric thresholds as scientific truth.

`source_position` preserves zero-based identity even when labels are duplicated.
`interval_alignment` is `previous`, `next`, or `None`; it is supplied only by
verified reader semantics or an explicit override, never a generic alias.
Reader hints and recognition models SHALL carry this information through to
reconstruction rather than infer it from chunk contents.

---

# 23. Recognition states

Internally, recognition SHOULD distinguish at least:

```text
resolved
ambiguous
unresolved
explicit
```

Explicit user mappings SHALL be considered authoritative unless invalid.

---

# 24. Alias registry architecture

Aliases SHOULD be represented declaratively rather than embedded entirely in Python control flow.

Generic aliases and vendor-specific aliases SHALL remain separable.

Recommended conceptual structure:

```text
aliases/
    generic/
        time.yaml
        current.yaml
        voltage.yaml
        capacity.yaml

    biologic/
        aliases.yaml

    neware/
        aliases.yaml
```

The final storage format MAY be YAML, TOML, JSON, or another human-readable declarative representation.

Human editability is an important design requirement.

---

# 25. Alias contribution workflow

Adding a new known header SHOULD require approximately:

1. adding an alias or rule;
2. adding a recognition test;
3. optionally adding a fixture.

Contributors SHOULD NOT need to modify the central scoring algorithm for ordinary aliases.

---

# 26. Generic and vendor-specific aliases

Recognition evidence SHALL conceptually combine:

```text
generic aliases
+
vendor-specific aliases
+
unit evidence
+
negative evidence
+
explicit reader knowledge
```

Vendor-specific knowledge SHALL receive appropriate priority when the source format is known.

---

# 27. Unit system

Version 0.1 SHOULD use a small internal unit-conversion system rather than a general-purpose physical-units framework.

The supported units are deliberately narrow and domain-specific.

This reduces:

- dependency weight;
- hidden behavior;
- ambiguity;
- implementation complexity.

---

# 28. Unit whitelist

Only explicitly supported units SHALL be converted automatically.

Examples include:

### Time

```text
s
ms
µs
us
min
h
day
```

### Current

```text
A
mA
µA
uA
nA
```

### Voltage

```text
V
mV
µV
uV
```

### Capacity

```text
Ah
mAh
µAh
uAh
C
```

Additional units SHALL require explicit implementation and tests.

---

# 29. Unit compatibility

The unit subsystem SHALL validate dimensional compatibility.

Examples:

```text
mA → current      valid
V  → current      invalid

mV → voltage      valid
s  → voltage      invalid
```

An incompatible explicit unit mapping MUST raise an error.

---

# 30. `iter_read()`

`iter_read()` SHALL be the public chunk-processing API.

Conceptually:

```python
for chunk in iter_read("huge.csv"):
    ...
```

Every yielded chunk SHALL already conform to the canonical schema:

```text
time_s
current_mA
voltage_V
```

Users SHALL NOT be required to normalize chunks themselves.

A chunk is a fragment of one logical dataset, not an independently normalized
dataset. Its columns and dtypes are canonical, but its time need not begin at
zero and an individual chunk may contain only missing time. The first-finite
origin and whole-source validity requirements apply across the complete
iterator. Accordingly, `is_standardized(chunk)` may be `False` for a valid
fragment; individual fragments are not independent inputs to `merge()`.

---

# 31. `read()` versus `iter_read()`

The meaning of the two APIs SHALL remain distinct:

```text
read()
    → one complete pandas DataFrame

iter_read()
    → iterator of standardized pandas DataFrames
```

`read(chunksize=...)` SHALL NOT be used to change the return type.

This avoids polymorphic and surprising behavior.

---

# 32. Chunk size

`iter_read(path, *, chunk_size=250_000, **read_options)` SHALL expose a positive
integer chunk size and the same interpretation options as `read()`.

Conceptually:

```python
iter_read(
    "huge.csv",
    chunk_size=250_000,
)
```

The reference default is 250,000 rows. Yielded chunks contain at most this many
rows; a reader may return smaller chunks. A non-streaming vendor backend may
materialize the source before yielding chunks, and this limitation must be
declared in its capabilities and documentation.

Chunk size MUST NOT change scientific results.

---

# 33. Stateful chunk processing

Internal pipeline components SHALL be allowed to maintain state across chunk boundaries.

Examples:

```python
previous_time
previous_capacity
previous reconstruction state
```

State SHALL belong to the conversion operation and MUST NOT leak between unrelated files.

The time origin is the first finite time of the entire source; chunks do not
restart at zero. Leading rows with missing time retain `NaN`. Reconstruction
uses adjacent original rows, so state must also preserve missing boundary rows.
`next` interval alignment requires one-row lookahead across chunk boundaries
and gives only the final logical row its endpoint `NaN`.

Whole-source checks, including the existence of a finite time and at least one
finite reconstructed current, finish when the iterator is exhausted. Therefore
`iter_read()` may raise after yielding earlier chunks. Consumers must exhaust
the iterator to establish complete-file success. Warning categories, affected
columns, and aggregate affected-row counts SHALL be equivalent across chunk
sizes; the number of warning emissions need not be identical.

---

# 34. pandas as public representation

Canonical in-memory datasets and yielded public chunks SHALL be pandas DataFrames.

This simplifies:

- user interoperability;
- downstream integration;
- testing;
- scientific usability.

---

# 35. PyArrow as internal engine

PyArrow SHOULD be available as a core implementation dependency.

It MAY be used for:

- Parquet reading;
- Parquet writing;
- delimited text ingestion;
- column selection;
- streaming;
- memory-efficient conversions;
- reduced copying.

Internal use of Arrow MUST remain invisible to ordinary pandas users unless explicitly documented.

---

# 36. `convert()`

`convert()` SHALL provide high-level file-to-file conversion.

Conceptually:

```python
convert(
    "experiment.mpr",
    "experiment.parquet",
)
```

The destination format SHALL normally be inferred from the output filename.

---

# 37. Explicit output format

Advanced users MAY override format inference.

Conceptually:

```python
convert(
    source,
    destination,
    format="parquet",
)
```

An explicit format SHALL take precedence over extension inference.

---

# 38. Overwrite behavior

Existing destination files MUST NOT be overwritten silently.

This policy applies equally to `write()` and `convert()`.

Default behavior:

```text
destination exists
        ↓
raise error
```

Users MAY opt into overwrite:

```python
convert(
    source,
    destination,
    overwrite=True,
)
```

---

# 39. Streaming conversion

`convert()` SHOULD use streaming/chunk-based processing where supported.

It SHOULD NOT internally call:

```python
df = read(...)
df.to_parquet(...)
```

for arbitrarily large sources when a streaming route exists.

`convert(source, destination, *, format=None, overwrite=False,
chunk_size=250_000, **read_options)` SHALL consume the complete source and return
the destination as a `pathlib.Path` only after successful final validation.
Required v0.1 destinations are Parquet, CSV, and TXT; Excel is deferred.

Conversion SHALL write to a temporary file in the destination directory and
publish it only after the iterator, writer, and final checks all succeed.
On failure, remove the operation's temporary file and preserve any previous
destination. With `overwrite=False`, publication must also refuse a destination
created during conversion. Output must never appear complete after a late
streaming validation failure. Existing user files are never cleanup targets.

---

# 40. `write()`

A generic standardized-data writer SHOULD be exposed.

Conceptually:

```python
write(
    df,
    "output.parquet",
)
```

The DataFrame MUST be canonical or safely validated before writing.

`write(df, destination, *, format=None, overwrite=False)` returns a
`pathlib.Path` on successful publication and uses the same temporary-output and
overwrite policy as `convert()`. File suffix inference supports `.parquet`,
`.csv`, and `.txt`; an explicit `format` may select `parquet`, `csv`, or `txt`.
The reference text output uses UTF-8, decimal point, no index, a header, and
comma separation for CSV or tab separation for TXT. Destination text dialect
customization and Excel export are deferred beyond v0.1.

---

# 41. Canonical-data validation before write

`write()` MUST NOT silently accept arbitrary three-column data merely because names happen to match.

It SHOULD validate:

- exact required columns;
- numeric compatibility;
- time monotonicity;
- expected canonical dtypes after conversion;
- missing values.

An accepted dataset is nonempty, has exactly the three canonical columns in
canonical order, and has at least one finite time. The first finite time is
zero, finite times are non-decreasing even across missing rows, and infinity is
invalid in every canonical column. `NaN` is retained and warned. `write()` may
convert compatible numeric dtypes to `float64` but does not shift time, reorder
rows, or discard extra columns to repair invalid input.

---

# 42. Reading standardized output

The library SHALL be able to read its own standardized output.

At minimum:

```text
.parquet
.csv
.txt
```

files produced by the library SHOULD be recognized.

---

# 43. Standardized Parquet reader

Canonical Parquet output SHOULD have a dedicated optimized reader path.

When canonical schema is already present:

```text
time_s
current_mA
voltage_V
```

the reader SHALL avoid unnecessary general-purpose recognition.

It SHALL still validate the data.

---

# 44. Canonical dtype enforcement

If a standardized input contains:

```text
time_s float32
```

it SHALL be converted to canonical:

```text
time_s float64
```

Equivalent conversion applies to current and voltage.

---

# 45. `is_standardized()`

A helper SHOULD be exposed.

Conceptually:

```python
is_standardized(df) -> bool
```

It SHALL test whether a DataFrame conforms to the canonical schema sufficiently for downstream operations.

A stricter internal validation function MAY provide richer diagnostics.

`is_standardized()` is a read-only, warning-free predicate: it returns `True`
only for a pandas DataFrame satisfying the complete canonical contract,
including exact `float64` dtypes and order, nonempty data, a finite time origin
of zero, monotonic finite times, and no infinities. Retained `NaN` values are
allowed. It performs no dtype conversion or scientific repair.

---

# 46. Schema version

The package SHALL expose the canonical schema specification version.

Conceptually:

```python
SCHEMA_VERSION = "0.1"
```

Changes to canonical column meaning or required fields SHALL require a specification version change.

---

# 47. `merge()`

`merge()` SHALL operate only on already-standardized pandas DataFrames.

Conceptually:

```python
merged = merge([
    df1,
    df2,
    df3,
])
```

It SHALL NOT automatically read proprietary source files.

This keeps normalization and concatenation as separate responsibilities.

---

# 48. Merge validation

Every input passed to `merge()` MUST first satisfy canonical validation.

Non-standardized inputs SHALL raise:

```python
IncompatibleDataError
```

or another suitable domain-specific exception.

An empty input collection or an empty/all-NaN-time input raises
`IncompatibleDataError`. A single valid input returns an independent canonical
DataFrame. Merge SHALL NOT mutate any input DataFrame.

---

# 49. File-level multi-source conversion

A separate high-level function MAY handle direct multi-file conversion in a
future release. `convert_many()` and streaming merge-to-file are explicitly
deferred beyond v0.1 and are not acceptance requirements.

Possible future API:

```python
convert_many(
    ["part1.mpr", "part2.nda"],
    "merged.parquet",
)
```

It would conceptually perform:

```text
read/stream file A
        ↓
standardize
        ↓
read/stream file B
        ↓
standardize
        ↓
continuous-time merge
        ↓
write output
```

The exact public name SHALL be finalized when this deferred feature is designed.

---

# 50. Large merged outputs

A future multi-file conversion path SHOULD be capable of writing directly to
disk without constructing the complete merged DataFrame in memory. Version 0.1
provides in-memory `merge()` and single-source streaming `convert()`.

This is particularly important for multi-gigabyte input.

---

# 51. Bridge interval search

When merging datasets, the implementation SHALL search for a valid positive sampling interval.

For the preceding dataset, it SHOULD search backwards from the end until a valid positive finite `dt` is found.

For the next dataset, fallback SHALL search forward from the beginning.

The search MAY consider the complete relevant dataset if necessary.

---

# 52. NaN-aware merge interval detection

Bridge candidates SHALL use only two adjacent original rows whose times are
both finite. Skip an invalid candidate pair rather than filtering out `NaN`
rows and creating a new interval across them. Zero differences are skipped;
backward finite time or infinity already fails canonical validation.

The merge offset uses the preceding dataset's last finite timestamp and the
following dataset's first finite timestamp. Leading, internal, and trailing
`NaN` time rows remain in their original positions with `NaN` time unchanged.
If neither adjacent dataset supplies a positive interval, merging fails.

For example, preceding times `[0, NaN, 10, 10]` supply no bridge interval. With
following times `[0, 5]`, use the following interval of 5 seconds, producing
`[0, NaN, 10, 10, 15, 20]`. Monotonicity validation still compares finite times
across missing rows; bridge estimation and monotonicity are different checks.

No bridge interval may be inferred from:

```text
NaN
infinity
zero dt
negative dt
```

---

# 53. Warning architecture

Warnings SHALL use Python's standard `warnings` framework.

The library SHOULD define warning subclasses.

Examples:

```python
class DataStandardizationWarning(UserWarning):
    ...

class MissingValueWarning(DataStandardizationWarning):
    ...

class PartialRecoveryWarning(DataStandardizationWarning):
    ...
```

Users may therefore use standard Python filtering:

```python
import warnings

warnings.filterwarnings(
    "ignore",
    category=MissingValueWarning,
)
```

No custom warning suppression framework is required.

---

# 54. Logging architecture

Logging and warnings SHALL remain distinct.

### Warnings

User-relevant scientific or data-quality conditions.

### Logging

Developer/debugging details.

The implementation SHALL use Python's standard `logging` module.

---

# 55. Malformed rows

The library MUST NOT silently discard malformed scientific rows by default.

Preferred behavior hierarchy:

1. retain row with explicit missing values if parsing remains safe;
2. emit warning;
3. stop if safe interpretation is impossible.

Automatic row skipping SHOULD NOT be the default.

A future explicit recovery policy MAY allow users to choose more permissive behavior.

---

# 56. Exceptions

All library-specific exceptions SHOULD derive from one package base exception.

Conceptually:

```python
class DataStandardizationError(Exception):
    pass
```

Examples:

```python
UnsupportedFormatError
MissingColumnError
AmbiguousColumnError
UnknownUnitError
InvalidUnitError
CurrentReconstructionError
NonMonotonicTimeError
IncompatibleDataError
CorruptedFileError
MissingDependencyError
OutputExistsError
```

---

# 57. Missing optional dependency

Attempting to use unavailable vendor support SHALL produce an actionable error.

Example:

```text
Bio-Logic support is not installed.

Install it with:

    pip install battread[biologic]
```

Generic `ImportError` messages SHOULD NOT leak directly to ordinary users.

---

# 58. Dependency groups

Vendor dependencies SHOULD be isolated using optional dependency groups.

Conceptually:

```bash
pip install battread
```

installs the core and generic standardized-data functionality.

Vendor support may use:

```bash
pip install battread[biologic]
pip install battread[neware]
pip install battread[all]
```

Exact packaging depends on dependency compatibility.

---

# 59. Core dependencies

The core dependency set SHOULD remain deliberately small.

Expected central dependencies include approximately:

```text
numpy
pandas
pyarrow
```

Additional generic parsing dependencies MAY be added if justified.

Vendor-specific packages SHALL remain optional where practical.

---

# 60. Bio-Logic backend

The Bio-Logic reader MAY rely on Galvani or another compatible backend.

The backend SHALL be isolated within the Bio-Logic reader module.

No generic core component shall import Galvani directly.

This limits licensing and dependency coupling.

---

# 61. Neware backend

The Neware reader MAY rely on NewareNDA or another compatible backend.

Equivalent isolation requirements apply.

---

# 62. Reader documentation contract

Every vendor reader SHOULD have dedicated documentation containing:

- supported extensions;
- underlying parser dependency;
- dependency license;
- tested parser versions;
- streaming support;
- known limitations;
- recognized source quantities;
- current reconstruction behavior;
- installation instructions;
- representative examples.

---

# 63. Configuration philosophy

Version 0.1 SHOULD favor explicit function parameters over a mandatory configuration object.

Example:

```python
read(
    path,
    reader=...,
    columns=...,
    units=...,
)
```

A future immutable `ReadConfig` MAY be introduced when configuration serialization becomes useful for GUIs or reproducible pipelines.

---

# 64. Internal typed configuration

Internal implementation MAY use immutable dataclasses even when the public API exposes simple keyword arguments.

This is encouraged.

Examples include:

```text
ReadOptions
RecognitionOptions
ExportOptions
MergeOptions
```

---

# 65. Type hints

All public APIs MUST have complete type annotations.

Internal modules SHOULD also use type annotations extensively.

Typing is considered part of maintainability rather than only documentation.

---

# 66. Static type checking

Static type checking SHALL be part of CI.

Recommended tool:

```text
pyright
```

Mypy MAY be used instead if implementation constraints favor it.

The project SHOULD select one primary static checker to avoid redundant configuration.

---

# 67. Code-quality toolchain

Recommended development tools:

```text
ruff
pytest
pyright
pre-commit
```

Ruff SHOULD provide linting and formatting.

Tests SHALL use pytest.

---

# 68. Continuous integration

CI SHOULD include at least:

```text
format/lint check
static type check
unit tests
integration tests
package build
```

Supported Python versions SHOULD be exercised according to project policy.

---

# 69. Minimum Python version

The initial target SHALL be:

```text
Python >= 3.11
```

A higher minimum MAY be chosen if required by critical dependencies, but compatibility SHALL be evaluated before implementation.

---

# 70. Documentation framework

Project documentation SHOULD use:

```text
MkDocs
+
Material for MkDocs
```

unless implementation discovers a compelling reason to choose another system.

---

# 71. Documentation structure

Recommended documentation:

```text
docs/
├── index.md
├── getting-started.md
├── user-guide/
│   ├── reading.md
│   ├── recognition.md
│   ├── merging.md
│   ├── exporting.md
│   └── large-files.md
│
├── readers/
│   ├── biologic.md
│   ├── neware.md
│   └── generic-text.md
│
├── api/
│   └── ...
│
├── architecture/
│   └── ...
│
├── specification/
│   └── ...
│
└── contributing/
```

---

# 72. API documentation

Public APIs SHOULD be generated or cross-referenced automatically from docstrings where practical.

Every public function SHALL document:

- purpose;
- parameters;
- return value;
- exceptions;
- warnings;
- at least one example where useful.

---

# 73. Testing fixtures

Small representative vendor files SHOULD be stored under:

```text
tests/data/
```

when:

- redistribution is legally permitted;
- files contain no sensitive information;
- repository size remains reasonable.

---

# 74. Fixture policy

Fixtures SHALL be as small as possible while preserving the behavior being tested.

Separate fixtures SHOULD cover edge cases rather than relying on one very large experimental file.

---

# 75. Large benchmark data

Large files SHALL NOT normally be committed to the main repository.

Performance benchmarks MAY use:

- generated datasets;
- external optional datasets;
- local benchmark fixtures.

Ordinary CI SHOULD remain reasonably lightweight.

---

# 76. Custom aliases at runtime

The architecture SHOULD allow future runtime extension of recognition aliases.

Version 0.1 does not need to expose a fully general plugin-quality alias API.

The internal recognizer SHALL nevertheless avoid global hard-coded structures that make runtime extension impossible.

---

# 77. Public API simplicity

The preferred user experience is:

```python
from battread import read, merge, convert
```

rather than requiring users to understand internal modules.

Advanced APIs MAY remain available from submodules.

---

# 78. Public versus internal API

Only explicitly documented top-level functions and documented data structures SHALL be considered stable public APIs.

Internal modules MAY evolve during `0.x` development.

Internal names SHOULD use clear conventions where appropriate to discourage accidental dependence on unstable implementation details.

---

# 79. Parquet canonical contract

A Parquet file written by the library SHALL be readable without any original vendor dependency.

It MUST contain sufficient tabular information to recover:

```text
time_s      float64
current_mA  float64
voltage_V   float64
```

No Galvani, NewareNDA, Bio-Logic software, or Neware software shall be required to consume canonical Parquet output.

---

# 80. Parquet metadata

Version 0.1 SHALL NOT require custom scientific metadata in Parquet files.

The canonical schema itself is the contract.

Optional schema-version metadata MAY be considered if it does not complicate interoperability.

---

# 81. Standardized CSV/TXT recognition

Canonical text exports using:

```text
time_s
current_mA
voltage_V
```

SHOULD be recognized immediately as already-standardized data.

General alias scoring SHOULD be bypassed when the canonical schema can be established directly.

---

# 82. Data-copy minimization

Internal operations SHOULD avoid unnecessary DataFrame copies.

Where safe, column selection, dtype conversion, Arrow operations, and chunk processing SHOULD be designed to minimize peak memory consumption.

Performance optimizations MUST NOT compromise correctness.

---

# 83. Benchmark policy

Version 0.1 SHALL establish benchmarks but SHALL NOT define arbitrary throughput requirements before real implementation measurements exist.

Benchmark baselines SHOULD include:

- delimited reading;
- recognition overhead;
- canonical normalization;
- current reconstruction;
- merge;
- Parquet export;
- peak RAM.

Future versions MAY establish quantitative regression thresholds.

---

# 84. Extension contract for future readers

A future reader SHOULD be implementable by:

1. subclassing or satisfying the reader protocol;
2. declaring capabilities;
3. implementing detection;
4. implementing inspection;
5. implementing reading;
6. optionally implementing streaming;
7. providing vendor aliases and semantics;
8. registering the reader;
9. supplying tests and documentation.

No modification to canonical normalization logic should ordinarily be required.

---

# 85. Separation between parser and semantics

Vendor parser code and semantic recognition SHOULD remain conceptually distinct.

Example:

```text
Bio-Logic parser
      ↓
source fields
      ↓
Bio-Logic semantic hints
      ↓
generic recognition/normalization
```

This makes it possible to replace an underlying parser without rewriting the rest of the pipeline.

---

# 86. Source dependency replacement

The architecture SHALL allow an underlying parser such as Galvani or NewareNDA to be replaced later without changing the public API.

Users SHOULD not observe which backend parser is being used except through documentation or inspection/debug information.

---

# 87. GUI compatibility

The library SHALL not depend on any GUI framework.

GUI applications SHALL depend on the library, never the reverse.

The public API SHOULD provide sufficient information for a GUI to:

- inspect files;
- show filenames;
- show file sizes;
- identify formats;
- display detected columns;
- reorder files;
- initiate conversion;
- initiate merge;
- report warnings and errors.

---

# 88. File size information

File inspection MAY expose basic filesystem information such as:

```text
filename
file size
detected format
```

This is operational information and does not constitute scientific metadata in standardized output.

---

# 89. Threading and parallelism

Version 0.1 SHALL NOT require parallel execution as part of the core scientific behavior.

The architecture SHOULD avoid unnecessary global mutable state so that future GUI or batch workflows can process independent files concurrently.

Parallel processing MAY be introduced separately after profiling demonstrates value.

---

# 90. Determinism

Given:

- the same input file;
- the same explicit options;
- the same compatible parser behavior;

the library SHOULD produce deterministic standardized output.

Recognition order MUST NOT depend on unordered data structures or incidental filesystem behavior.

---

# 91. Global mutable state

Scientific behavior SHALL NOT depend on mutable global configuration.

Reader registries and alias registries MAY be initialized globally but SHOULD be treated predictably.

Per-call overrides MUST remain local to the operation.

---

# 92. Security and robustness

Source files shall be treated as untrusted input.

Parsers SHOULD avoid:

- arbitrary code execution;
- unsafe deserialization;
- shell invocation where unnecessary;
- uncontrolled temporary-file behavior.

Third-party reader limitations SHOULD be reviewed and documented.

---

# 93. User-facing errors

Errors SHALL explain:

1. what failed;
2. what the library found;
3. what the user can do next where applicable.

Poor error:

```text
KeyError: 7
```

Preferred error:

```text
No usable current column was found.

A capacity candidate named "Capacity (mAh)" was detected,
but its semantics are ambiguous.

Provide an explicit current column or capacity interpretation.
```

---

# 94. API stability during 0.x

Top-level APIs may evolve during early development.

Breaking changes SHALL:

- be documented;
- be included in the changelog;
- avoid unnecessary churn.

Once a public API proves stable, compatibility SHOULD be preserved where practical.

---

# 95. Initial top-level API target

Version 0.1 should aim to expose approximately:

```python
from battread import (
    read,
    iter_read,
    inspect,
    detect_format,
    merge,
    convert,
    write,
    is_standardized,
)
```

Not all convenience functions need to exist in the earliest internal prototype.

---

# 96. Initial implementation priority

Recommended development order:

### Phase 1 — Canonical core

Implement:

```text
canonical schema
unit conversion
validation
merge
exceptions
warnings
```

### Phase 2 — Recognition

Implement:

```text
header normalization
alias registry
unit recognition
candidate scoring
ambiguity handling
```

### Phase 3 — Generic reader

Implement:

```text
CSV
TXT
delimiter detection
decimal detection
manual mappings
chunking
```

### Phase 4 — Standardized formats

Implement:

```text
Parquet read/write
canonical CSV/TXT
streaming conversion
```

### Phase 5 — Bio-Logic

Integrate and isolate Bio-Logic backend.

### Phase 6 — Neware

Integrate and isolate Neware backend.

### Phase 7 — Large-file optimization

Profile and optimize:

```text
PyArrow
copy minimization
chunk sizes
Parquet row groups
```

### Phase 8 — Documentation and stabilization

Finalize:

```text
user guide
reader documentation
contributor guide
benchmarks
API docs
```

---

# 97. v0.1 architectural success criteria

The architecture can be considered successful when:

1. generic CSV/TXT and supported vendor files use the same public API;
2. vendor readers remain isolated;
3. aliases can be extended without rewriting recognition algorithms;
4. ambiguity is represented explicitly;
5. canonical output is always identical in structure;
6. chunked and non-chunked processing give equivalent results;
7. Parquet conversion does not inherently require loading complete datasets into memory;
8. downstream code never needs vendor libraries;
9. new readers can be added without modifying existing ones substantially;
10. users can perform common operations using simple top-level functions.

---

# 98. Architectural guiding principle

The architecture shall make the simple case simple:

```python
df = read("experiment.mpr")
```

while preserving a clear route to explicit control:

```python
df = read(
    "unusual_data.txt",
    columns={
        "time": 0,
        "current": 3,
        "voltage": 7,
    },
    units={
        "time": "s",
        "current": "mA",
        "voltage": "V",
    },
    autodetect=False,
)
```

Automatic behavior shall be convenient.

Explicit behavior shall remain authoritative.

Internal complexity shall not leak unnecessarily into ordinary scientific workflows.
