# Sole implementation priority: memory-bounded MPR reading

Status: implemented for supported Galvani schemas on 2026-10-06. Unknown binary
field definitions remain unsupported and require independent verification.

This was the sole implementation priority after the GUI work. Bounded ingestion
now replaces the full-memory loading path. Evidence and architectural decisions
are recorded in [ADR 0006](../adr/0006-memory-bounded-mpr-ingestion.md), the reader
tests and the synthetic memory benchmark. Other enhancements remain deferred
until the maintainer selects the next priority.

## Required change

Replace the Bio-Logic MPR ingestion path that loads the complete measurement
module and creates large intermediate copies. The original public chunked API
bounded downstream conversion buffers but not the backend's initial allocation.
The new adapter scans small metadata and reads bounded structured batches.

Implement genuinely memory-bounded ingestion inside the Bio-Logic adapter, using
memory mapping or bounded file reads as appropriate. Evaluate reuse of Galvani's
field/layout definitions without relying on its full-memory MPR loading path.
Do not modify an installed Galvani package manually. Keep vendor dependencies
isolated and preserve the documented public API.

## Completion criteria

- Preserve canonical float64 values, original row order and missing rows.
- Preserve measured current and sign; reconstruct from verified dq only when
  measured current is absent, following existing scientific rules.
- Preserve time normalization, non-monotonic-time errors, ambiguity failures and
  relevant warnings. Do not repair scientific data to save memory.
- Compare the new path with the existing reader and independently verified
  references across supported layouts and chunk boundaries.
- Add regression tests for memory behavior, malformed/truncated modules and
  scientific equivalence. Use synthetic or independently licensed public data.
- Measure peak committed memory and physical RAM on representative sizes;
  demonstrate that ingestion buffers no longer scale as full-source copies.
- Record architectural decisions and update reader documentation, capabilities
  and limitations before declaring MPR ingestion streaming.

Private acquisitions, names, paths, hashes and data-specific measurements must
not be included in this document, tests or published benchmark artifacts.

## Remaining compatibility limitation

Field ID 215 is not defined by Galvani 0.5.0. Containers containing it now fail
early with UnsupportedFormatError rather than attempting a large allocation.
Do not infer its width or semantics from plausible values or total payload size.
Add support only with independently verified field layout/reference data and
regression tests. This is distinct from the solved full-source memory allocation.
