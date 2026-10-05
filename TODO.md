# Checklist for future releases

Updated on 2026-10-05. This list tracks future work; checks required before the
first publication remain in `RELEASE_STATUS.md`. When completing an item,
record the release version, added tests and verified result.

## Priority: Neware data

The current Neware workflow uses **CSV autoexports**. The `.nda`/`.ndax`
adapters remain available as experimental features: some layouts have only
synthetic fixture coverage. They are not required for Alessandro Gregucci's
current workflow.

- [ ] **Validate NDA/NDAX against complete real acquisitions.** Obtain
  redistributable files and matching exports from the same experiment. Compare
  every time, current and voltage row, including order, sign and units. Record
  instrument, software, layout, backend, provenance and reference. Completion:
  independent, chunk-equivalent tests for each declared layout, covering
  positive/negative current, rest and step changes.
- [ ] **Investigate binary records currently rejected.** In particular, NDA
  `AA` framing, conflicting NDAX checkpoints and the distinction between padding
  and final zero-valued measurements. Obtain examples and verified semantics
  before changing parsing. Completion: regressions demonstrating no row loss or
  arbitrary scientific repair; otherwise retain explicit errors.
- [ ] **Expand CSV autoexport profiles.** Collect headers, delimiters and time
  formats beyond the current sample. Verify Total Time against resetting step
  time. Completion: explainable recognition and tests for each profile, with
  explicit mapping wherever ambiguity remains.
- [ ] **Reassess experimental binary support.** Promote only sufficiently
  verified layouts and update reader guides, README and acceptance reports.
  Do not extrapolate format-version coverage to all instruments.

## Performance and large files

- [ ] **Benchmark multi-GB files and wider tables.** Repeat timing and peak-RAM
  measurements across sizes and chunks, including NaN, duplicate times and
  reconstruction. Completion: scientifically equivalent streaming and memory
  explained in terms of chunks, metadata and buffers, without invented targets.
- [ ] **Evaluate a memory-bounded MPR reader.** Profile Galvani and investigate
  alternatives before replacement. Completion: independent export comparisons,
  equivalent values/warnings/errors and measured RAM. Currently iter_read does
  not prevent the MPR backend from loading the entire source.
- [ ] **Evaluate PyArrow CSV as a fast path.** The current probe measures parsing
  alone. Before integration, demonstrate equivalent dialects, clock handling,
  units, malformed cells, duplicate labels, warnings and errors, plus a measured
  performance benefit.
- [ ] **Profile current reconstruction.** Optimize only after measurement,
  preserving original adjacency, previous/next alignment, endpoints, reset
  handling and state across chunks. Completion: regressions and before/after
  benchmarks.

## Maintenance after publication

- [ ] **Validate macOS and ARM environments.** The initial release checks cover
  Windows and Ubuntu x86-64. Run installed-wheel, optional-backend and minimum
  dependency checks on additional platforms before claiming verified support.
- [ ] **Verify dependency upgrades.** Run the CI matrix, supported minimum
  dependency tests, vendor fixtures and artifact checks. Reaudit NewareNDA's
  private APIs before changing the pinned version.
- [ ] **Turn every real issue into a regression.** Retain a minimal
  redistributable example, expected interpretation and reason for the fix;
  update documented limitations.
- [ ] **Review installation, examples and notebooks for every release.** Test
  the installed wheel and retain a minimal example alongside detailed demos.
  Update the changelog and this checklist without claiming unperformed checks.
- [ ] **Keep public-facing material in English.** Review documentation, example
  notebooks, user-facing messages and contribution notes before publication.

Cycle, capacity and energy analysis, plotting and Excel remain outside the
library's scope. Any additional functionality requires a separate decision;
this checklist does not introduce it automatically.
