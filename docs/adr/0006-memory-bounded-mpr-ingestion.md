# ADR 0006: memory-bounded Bio-Logic MPR ingestion

Accepted on 2026-10-06. Supersedes ADR 0002's full-memory MPR limitation.

## Problem

Galvani 0.5's MPRfile constructor retains full module data and payload-sized
byte slices for field IDs and records. Smaller standardized chunks cannot bound
that initial allocation. Inspection also used the constructor unnecessarily.

## Decision

Retain Galvani as an optional, isolated schema dependency. Use its metadata-only
module iterator and dtype definitions, without invoking MPRfile. Normalize its
mutable descriptor offsets/lengths to Python ints before resuming the iterator,
preventing uint32 seek arithmetic from wrapping beyond 4 GiB.

Validate all module bounds and supported data headers before reading measurements.
Handle Galvani's known data versions 0 (two encodings), 2 and 3 and both module
header formats. Preserve reserved-byte, record-count, date, LOG timestamp and
loop-framing failures. Unknown column widths remain unsupported; no dtype
guessing, global backend-map edits or edits to installed Galvani are permitted.

Read ordinary file-backed structured arrays with explicit positive record counts
and an 8 MiB binary-buffer ceiling. Do not map the whole acquisition: explicit
reads avoid source-sized resident mappings and give deterministic handle lifetime
on Windows. Reuse the existing conversion/reconstruction pipeline unchanged.
For wide schemas, reduce the effective standardized chunk size using a documented
source-cell buffer heuristic; the public contract permits smaller chunks.

Metadata inspection reads bounded prefixes and seeks over payloads. Open record
handles lazily and close them on exhaustion, error or explicit iterator close.
Check file identity, size and modification time before/after ingestion to reject
stale or changing sources. Consumers must still exhaust the iterator for complete
scientific validation. Atomic convert() publication remains unchanged.

## Consequences and evidence

- MPR advertises source streaming; read() still collects the full canonical result.
- Public API, measured-current precedence/sign, dq semantics, NaN retention and
  conservative ambiguity/time checks are unchanged.
- Independent wire fixtures cover layout variants, corruption, cancellation and
  oversized/invalid batch requests. Existing independently exported fixtures and
  Galvani comparisons cover scientific equivalence.
- Fresh-process synthetic ingestion measurements are stored in
  `benchmarks/mpr-memory.json`; they measure ingestion, not complete normalization.
- Unsupported ID 215 remains an explicit schema failure. Its presence/width cannot
  be accepted based on plausible values or payload-size arithmetic. Verification
  requires an independently established layout/reference before support is added.

The byte ceiling is not a promise of total process RAM: imports, caller-retained
frames, source-width strings, conversion state and output writers also consume
memory. No throughput targets are introduced.
