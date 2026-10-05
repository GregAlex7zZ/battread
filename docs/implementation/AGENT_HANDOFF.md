# Implementation Handoff Brief

## 1. Mission

Implement a new open-source Python library for vendor-independent standardization of electrochemical cycling data.

The library converts supported source files into a canonical dataset containing:

```text
time_s      float64
current_mA  float64
voltage_V   float64
```

The library is an ingestion and standardization layer.

It is not an electrochemical-analysis package.

---

# 2. Read these documents first

Implementation decisions must follow, in order of authority:

```text
docs/specification/TECHNICAL_SPECIFICATION.md
docs/specification/COLUMN_RECOGNITION.md
docs/architecture/ARCHITECTURE_AND_API.md
docs/specification/INITIAL_RECOGNITION_REGISTRY.md
docs/testing/TESTING_AND_ACCEPTANCE.md
```

Where two documents appear inconsistent:

1. prefer the more specific document;
2. preserve scientific conservatism;
3. document the discrepancy before changing externally observable behavior.

Do not silently reinterpret requirements.

The preimplementation clarifications accepted on 2026-10-04 are recorded in
`docs/adr/0001-v0.1-contract-clarifications.md` and incorporated into the
specification and API documents. Read that record after the documents above
to understand the decisions and their reasons. These are normative v0.1
clarifications, not optional implementation suggestions.

The distribution and Python import name are both `battread`. `README.md`,
`pyproject.toml`, `LICENSE`, and `THIRD_PARTY_NOTICES.md` live at the project
root. Project URLs and named authors must be supplied by the maintainer before
publication; do not invent them. The repository currently contains documents
and packaging configuration, with no implemented library yet.

---

# 3. Non-negotiable scientific behavior

The implementation must preserve these invariants:

```text
canonical output:
time_s
current_mA
voltage_V
```

with `float64`.

The library must:

- normalize time to start from zero;
- preserve directly measured current sign;
- prefer direct current over reconstructed current;
- never reconstruct current from semantically ambiguous capacity;
- never silently delete NaN rows;
- reject backward-moving time;
- never silently resolve real column ambiguity;
- never use arbitrary column position as semantic evidence for generic files;
- keep cycle/half-cycle analysis out of this package.

In addition:

- retain leading and trailing missing-time rows; the first finite time is zero;
- reject empty datasets, datasets without finite time, and canonical infinities;
- use adjacent original rows for reconstruction and merge sampling intervals;
- require declared `previous` or `next` alignment for incremental capacity;
- treat negative signed capacity changes as potentially legitimate discharge;
- reject known capacity resets without attempting generic repair;
- retain missing direct current, including an all-NaN selected current column;
- publish converted files only after full-source validation succeeds.

---

# 4. Initial supported sources

Implement:

```text
Bio-Logic:
.mpr
.mpt

Neware:
.nda
.ndax

Generic:
.csv
.txt

Canonical:
.parquet
canonical .csv/.txt
```

Arbin is explicitly deferred.

---

# 5. Dependency strategy

Core dependencies should remain small.

Expected core:

```text
numpy
pandas
pyarrow
```

Generic parsing dependencies may be added only when justified.

Vendor parsers must remain isolated behind optional extras.

Conceptually:

```text
battread[biologic]
battread[neware]
battread[all]
```

Do not import vendor parser packages from generic core modules.

At implementation time, verify current compatible releases and licenses before pinning dependency constraints.

---

# 6. Bio-Logic backend

Initial backend candidate:

```text
Galvani
```

The Bio-Logic adapter must isolate it completely behind the reader interface.

No other subsystem should depend directly on Galvani objects or field representations.

The adapter shall convert parser output into internal source-column information.

Backend replacement must remain possible without changing the public API.

---

# 7. Neware backend

Initial backend candidate:

```text
NewareNDA
```

Apply the same isolation requirements.

Do not leak NewareNDA-specific objects through the public API.

---

# 8. Implementation order

Proceed incrementally.

## Milestone 1 — repository foundation

Create:

```text
pyproject.toml
src layout
tests layout
docs layout
CI
ruff
pytest
pyright
pre-commit
MkDocs
```

The root packaging and license files already exist. Complete their setup rather
than recreate placeholder copies under `docs/`. Dependency constraints still
require a compatibility audit; the preliminary third-party inventory is not a
completed release audit.

Do not begin vendor-reader integration before the canonical core and testing infrastructure exist.

## Milestone 2 — canonical core

Implement:

```text
schema constants
exceptions
warnings
unit conversion
canonical validation
is_standardized()
merge()
```

## Milestone 3 — recognition core

Implement:

```text
header normalization
unit extraction
alias loading
candidate generation
negative evidence
ambiguity handling
ColumnMatch model
InspectionResult model
```

The recognition engine must be independently testable.

## Milestone 4 — generic delimited reader

Implement:

```text
CSV
TXT
separator detection
decimal separator detection
header handling
explicit positional mapping
explicit name mapping
unit overrides
sep/decimal/encoding/header/skiprows overrides
inspect()
read()
iter_read()
```

This reader is the primary proving ground for the recognition architecture.

## Milestone 5 — canonical formats

Implement:

```text
Parquet reader
Parquet writer
canonical CSV/TXT fast path
convert()
write()
```

Implement streaming Parquet conversion where practical.

## Milestone 6 — current reconstruction

Implement:

```text
signed cumulative capacity
signed incremental capacity
previous/next interval alignment
charge/discharge capacity pair
chunk-boundary state
ambiguity rejection
```

Do not expand capacity heuristics beyond the specification without tests.

## Milestone 7 — Bio-Logic

Integrate `.mpr` and `.mpt`.

Start with direct:

```text
time
current
voltage
```

Then implement known safe reconstruction cases.

Add representative regression fixtures.

## Milestone 8 — Neware

Integrate `.nda` and `.ndax`.

Add representative regression fixtures.

## Milestone 9 — large-data optimization

Profile before optimizing.

Investigate:

```text
PyArrow CSV
Arrow-backed conversion
Parquet row groups
copy minimization
chunk-size defaults
streaming multi-file conversion
```

Do not sacrifice correctness for benchmark performance.

## Milestone 10 — release preparation

Complete:

```text
README
user guide
reader docs
contributor guide
API docs
third-party notices
changelog
```

---

# 9. Reader architecture

Use class-based readers with a central registry.

Each reader should conceptually provide:

```python
can_read(...)
inspect(...)
read(...)
iter_read(...)
```

and declare its capabilities.

Do not implement format routing as a growing top-level extension `if/elif` chain.

---

# 10. Public API target

Top-level imports should eventually support:

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

`read()` must always return one complete pandas DataFrame.

`iter_read()` must return an iterator of already standardized DataFrames.

Do not make `read()` change return type when a chunk-size parameter is supplied.

---

# 11. Recognition architecture

Recognition should produce structured candidates rather than immediately returning strings.

Use immutable typed models where appropriate.

Conceptually:

```python
ColumnMatch(...)
InspectionResult(...)
ReaderCapabilities(...)
```

Recognition must be explainable.

`inspect()` should be able to expose why a column was selected or rejected.

---

# 12. Registry architecture

Alias data should be declarative and human-readable.

Keep:

```text
generic
Bio-Logic
Neware
```

rules separate.

Adding a normal alias should generally require:

```text
registry change
+
test
```

not recognition-engine code changes.

---

# 13. Fuzzy matching

Do not use fuzzy matching to make automatic scientific decisions.

It may later be used only to produce user suggestions.

Machine-learning or LLM-based recognition is outside v0.1.

---

# 14. Error policy

Use explicit domain exceptions.

All package exceptions should inherit from one package base exception.

Examples:

```text
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

User-facing messages must be actionable.

---

# 15. Warning policy

Use Python `warnings`.

Warnings and logging serve different purposes.

Warning:

```text
something the scientific user should know
```

Logging:

```text
implementation/debug details
```

Do not invent a custom warning-management system.

---

# 16. Large-file constraints

Assume individual source and output files may be several GB.

Avoid designs that inherently require repeated full DataFrame copies.

Generic text and Parquet processing should support chunked operation.

Vendor readers may have backend limitations; document them rather than pretending they stream.

Scientific output must be invariant to chunk size.

---

# 17. Merge

`merge()` accepts canonical DataFrames only.

It must not read proprietary files internally.

File-to-file multi-source workflows may use a separate convenience function later.

Merge order is user-defined.

Bridge time behavior must follow the Technical Specification exactly.

---

# 18. Licensing boundary

The standardization library is intended to be fully open source.

Vendor dependencies must nevertheless remain clearly isolated and documented.

Maintain:

```text
THIRD_PARTY_NOTICES.md
```

and document each backend's license.

Do not assume that repository separation changes dependency-license obligations.

The downstream analysis project consumes standardized output files and does not need to import this library.

---

# 19. Documentation requirements

Documentation quality is part of implementation quality.

The repository must be understandable without access to the original design conversation.

Prefer:

```text
plain language
small examples
clear module boundaries
explicit assumptions
accessible diagrams
actionable error explanations
```

Every reader must document:

```text
supported formats
dependency/backend
limitations
streaming capability
known semantics
installation extra
```

---

# 20. Do not over-engineer v0.1

Do not introduce without demonstrated need:

```text
database layer
GUI dependencies
distributed computing framework
plugin marketplace
machine learning
custom dataframe class
custom unit framework beyond domain needs
complex metadata model
cycle analysis
```

Design extension points where appropriate, but keep the initial implementation focused.

---

# 21. Decision policy during implementation

When an unspecified implementation detail is encountered:

1. preserve the public specification;
2. prefer the simplest modular implementation;
3. prefer deterministic behavior;
4. prefer explicit failure over scientific guessing;
5. add tests for the chosen behavior;
6. document important architectural decisions using ADRs.

Do not widen scientific behavior merely because it is technically easy.

---

# 22. Expected repository structure

A suitable target is:

```text
project-root/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── SECURITY.md
├── THIRD_PARTY_NOTICES.md
├── pyproject.toml
│
├── docs/
│   ├── specification/
│   ├── architecture/
│   ├── testing/
│   ├── user-guide/
│   ├── developer-guide/
│   ├── readers/
│   ├── api/
│   └── adr/
│
├── src/
│   └── battread/
│       ├── readers/
│       ├── recognition/
│       ├── normalization/
│       ├── reconstruction/
│       └── ...
│
├── tests/
│   ├── data/
│   ├── recognition/
│   ├── readers/
│   ├── integration/
│   └── ...
│
└── benchmarks/
```

---

# 23. Implementation completion report

When implementation is complete, provide a report containing:

```text
implemented features
public API
test results
type-check status
lint status
supported vendor formats
known limitations
streaming support by reader
benchmark summary
dependency/license summary
remaining TODOs
```

Also list any deliberate deviation from the specifications.

---

# 24. Final implementation objective

The finished v0.1 should make this simple:

```python
from battread import read

df = read("experiment.mpr")
```

while ensuring that a successful result means the software has a defensible reason for interpreting the source as:

```text
time_s
current_mA
voltage_V
```

Correctness must remain more important than maximizing automatic conversion success.
