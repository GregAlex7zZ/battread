# Changelog

## Unreleased

- Simplify public documentation and add an output-free introductory notebook
  with synthetic examples, large-file guidance and explicit column selection.

- Extend the verified opaque MPR overlay to accessory energy, impedance and
  step-time fields (115, 116, 175, 176, 177, 182); retain Galvani for known schemas
  and preserve explicit scientific ambiguity failures.

- Skip verified four-byte MPR field 215 as opaque padding using yadg's explicit
  layout definition; preserve other unknown-field errors and canonical values.

- Replace full-memory MPR ingestion with bounded metadata/record reads, while
  retaining Galvani's optional schema definitions and the public scientific API.
- Support metadata-only MPR inspection and deterministic iterator cleanup;
  validate container framing/counts and detect source mutation.
- Add layout/corruption/equivalence regressions and synthetic before/after memory
  evidence. Unsupported field IDs remain conservative explicit failures.

## 0.1.0

- Canonical float64 pandas schema, conservative recognition, unit conversion,
  validation and ordered merge of standardized DataFrames.
- Generic CSV/TXT, canonical Parquet/CSV/TXT, Bio-Logic MPR/MPT and experimental
  Neware NDA/NDAX readers; Neware CSV uses recognized Total Time.
- Measured-current precedence and signed capacity reconstruction only with
  established semantics; missing rows are retained and backward time fails.
- Streaming conversion and atomic output with safe overwrite behavior.
- Scientific regressions, licensed fixtures, Python compatibility CI and
  strict typing, lint and documentation checks.
