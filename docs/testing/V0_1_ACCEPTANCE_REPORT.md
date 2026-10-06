# v0.1 implementation acceptance report

Historical initial-release audit. The subsequent MPR ingestion change is
documented in [ADR 0006](../adr/0006-memory-bounded-mpr-ingestion.md) and the
[current reader guide](../readers/biologic.md); the original full-memory MPR
limitation below no longer describes the current supported-layout reader.

Audit date: 2026-10-05. Version **0.1.0** is prepared but not published.
Repository: https://github.com/GregAlex7zZ/battread. Copyright attribution and
version metadata are finalized. GitHub private vulnerability reporting has been
chosen; its activation and remote CI results require authenticated repository
access. See root RELEASE_STATUS.md for the publication checklist.
Windows/Linux Python 3.11-3.14 and minimum-core runtime and strict typing checks pass;
see [compatibility results](PYTHON_COMPATIBILITY.md). Original benchmark evidence
below was collected on Windows with Python 3.14.6.

Author and maintainer: Alessandro Gregucci, confirmed on 2026-10-05. Substantial
AI assistance in implementation, tests, notebooks and documentation is disclosed
in root AUTHORS.md. Automated checks do not establish independent human review.

## Implemented features and public API

The public functions are `read`, `iter_read`, `inspect`, `detect_format`, `merge`,
`write`, `convert` and `is_standardized`. `CANONICAL_COLUMNS` and `SCHEMA_VERSION`
are exported. pandas is the public table interface; the canonical schema is
ordered float64 `time_s`, `current_mA`, `voltage_V`.

Features include registry-based readers, deterministic declarative recognition,
unit recognition/conversion, normalized labels, negative evidence, structured
matches, inspectable ambiguity, explicit column/unit/parser overrides, canonical
validation, safe capacity reconstruction, chunk-boundary state and atomic output.
Direct current retains its sign and precedence even when all selected values
are missing. NaN rows remain with standard Python warnings. Non-monotonic time,
infinity, empty/all-missing-time data and unsupported inference fail explicitly.
Domain errors derive from DataStandardizationError and logging uses stdlib logging.

## Acceptance mapping

| Acceptance sections | Evidence |
|---|---|
| 3: schema, coercion, predicate | `test_validation.py`, `test_output.py`, canonical reader tests |
| 4–5: units and time | `test_units.py`, `test_time_normalization.py`, clock and large-streaming regressions |
| 6–8: recognition, ambiguity, duplicate positions | `tests/recognition/`, delimited reader tests |
| 9–11: current precedence and safe reconstruction | Reconstruction reader tests and Bio-Logic fixture tests |
| 12: NaN classes, counts, retained rows | Validation, reconstruction and chunk-warning tests |
| 13: merge and gap safety | `test_merge.py` |
| 14–17: canonical outputs, chunks, dialects, malformed data | Reader/output/integration tests, atomic late-failure tests |
| 18: Bio-Logic independent references | Attributed MPR/BT-Lab MPT export, synthetic capacity wire fixtures |
| 19: Neware independent references | NDA29/NDC16 wire-field references, synthetic fixtures for every declared layout |
| 20–23: regressions, API, errors, extras | Regression suite, package/API tests, missing-dependency tests and CI jobs |
| 24–25: performance and peak RAM | Fresh-process synthetic benchmarks for read, streaming, conversion, merge and other required operations |
| 26: documentation | README, user/API/reader/developer guides, license notices and contributor/release documents |

The local full suite has **608 passing tests** and **94% branch-aware total
coverage**. Ruff lint/format checks, strict public-API Pyright checking and
`pip check` pass. Strict MkDocs and wheel/source builds pass. Installed-wheel
smoke checks verify core round trips and vendor fixtures. Artifact review checks
schema registry data, license material and exclusion of private caches and samples.
Pre-commit is checked in an isolated Git snapshot selected by the publication
allowlist. Third-party fixtures and license texts are excluded from whitespace
rewriting so their bytes and independently recorded fingerprints are preserved.
Windows/Linux Python 3.11-3.14 and minimum-core checks pass. Remote CI remains
pending; local execution and GitHub Actions results are reported separately.

## Formats, references and streaming

| Format | Reader/backend | Streaming and limitations |
|---|---|---|
| Generic CSV/TXT | Native delimited reader | Chunked; malformed cells warned as NaN, structural errors fail |
| Canonical CSV/TXT | Canonical delimited path | Chunked; existing zero origin is validated |
| Canonical Parquet | PyArrow | Record batches; buffers and row groups also use memory |
| Bio-Logic MPT | Native text reader | Chunked; known dq reconstructed only without direct current |
| Bio-Logic MPR | Galvani 0.5.0 | Full backend load; chunks do not bound source RAM |
| Neware NDA | Isolated NewareNDA 2026.6.11 decoders | Records; layouts 29, 130 BTS9/BTS9.1 |
| Neware NDAX | Strict full/split NDC adapter | Layouts 2,5,11,14,16,17; split timestamp dictionary grows with checkpoint count |
| Neware CSV export profile | Generic reader | Total Time clock converted automatically to elapsed seconds |

Bio-Logic expectations come from the independent BT-Lab export, not Galvani.
Neware real-fixture expectations are manually specified wire-field references
for time, current and voltage, not backend-generated output. NDA current range
and split NDC unit assumptions are stated in the fixture provenance. Supplemental
layout fixtures are synthetic; they verify hand-declared values, signed current,
zero voltage, step-clock independence and chunk equivalence. They do not replace
future manufacturer-export comparisons or guarantee every hardware variant.
Provenance, license, hashes, tolerance and backend versions are in the fixture READMEs.

## Benchmarks and dependencies

One-million-row local CSV read improved from 4.842 to median 2.302 seconds;
streaming CSV-to-Parquet from 4.721 to 2.440 seconds. With 10k-row chunks,
generic streaming peaks at 97.1 MiB for 100k source rows and 97.4 MiB for 1M.
Complete read and merge grow with total result size. The initial comparison has
one before sample and three after samples; it is an indicative baseline, not a
universal performance target. See [benchmark methodology](../developer-guide/benchmarks.md).

Runtime dependencies: NumPy (BSD and bundled notices), pandas (BSD-3-Clause),
PyArrow (Apache-2.0 and bundled notices). Optional Galvani is GPL-3.0-or-later;
NewareNDA is BSD-3-Clause and pinned to its audited private decoder API.
The adapted Neware layout notice is included in wheel/source license files.
Bio-Logic test data retains CC-BY-4.0; Neware fixtures retain BSD-3-Clause.
Runtime dependencies and toolchain binaries are not bundled in battread artifacts.
The exact local transitive inventory and distribution boundaries are recorded
in root THIRD_PARTY_NOTICES.md.

## Known limits, remaining work and deliberate decisions

- Remote publication checks remain: verify the chosen security channel and
  GitHub Actions after an authorized upload. The actual release date is unset.
- Unknown Neware framing and conflicting timestamp checkpoints fail. Sparse
  NDAX timestamps remain warned NaN; no interpolation or row deduplication.
  Real NDA fixture coverage is a documented valid prefix, not its whole acquisition.
- MPR is constrained by Galvani's full-memory backend. Multi-GB and wider
  vendor benchmark coverage remains future work.
- Automatic Neware CSV Total Time selection is limited to the verified header
  profile; other variants need explicit mappings.
- Extra real Neware hardware acquisitions and independent manufacturer exports
  would strengthen the synthetic layout compatibility checks. On 2026-10-05
  the maintainer deferred that broader validation to future versions because
  the current Neware workflow uses CSV autoexports. Binary adapters are
  explicitly experimental; future verification is tracked in root TODO.md.
- Neware uses low-level backend decoders rather than its high-level sorter,
  deduplicator and interpolator (ADR 0004). This deliberately favors explicit
  failure over unsupported scientific repair.
- Bio-Logic dq preference follows the maintainer's instruction, documented in
  ADR 0003; measured current always wins.
- Citation metadata is omitted at the maintainer's request. Version 0.1.0 is
  prepared; publication remains a separate step.
- Multi-file streaming, cycle/half-cycle/energy/capacity analysis, plotting and
  Excel output remain out of scope. Arrow CSV integration is deferred until
  equivalent parsing and scientific validation can be demonstrated.

No known silent wrong-unit, wrong-column, row-loss, chunk-dependent or merge
offset defect remains in the supported verified fixtures. Unsupported files
still fail; successful fixture checks are not a guarantee for every vendor variant.
