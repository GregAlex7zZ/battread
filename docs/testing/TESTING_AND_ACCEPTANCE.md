# Testing & Acceptance Plan
## Version 0.1

**Status:** Implementation gate  
**Purpose:** Define objective acceptance criteria for the first usable library release.

---

# 1. Core principle

The project shall not consider numerical output sufficient evidence of correctness.

Tests must establish that quantities have the intended physical meaning, units, ordering, and transformations.

Scientific correctness takes priority over implementation convenience.

---

# 2. Test layers

The test suite shall include:

```text
unit tests
recognition tests
reader tests
integration tests
regression tests
round-trip tests
chunk-equivalence tests
performance benchmarks
```

---

# 3. Canonical schema tests

Every successful standardized result must contain exactly:

```text
time_s
current_mA
voltage_V
```

with:

```text
float64
float64
float64
```

respectively.

Tests shall verify:

- exact names;
- column order;
- dtype;
- no accidental source columns.

Empty datasets are invalid for v0.1. `read()`, `write()`, and `merge()` must reject them, and `is_standardized()` must return `False`, even when column names and dtypes are canonical. Nonempty datasets require at least one finite time value. An all-`NaN` time column must fail. Infinity in any canonical column is invalid; it must not be treated as a missing value.

Empty, all-`NaN` time, and infinite canonical datasets must raise `IncompatibleDataError` when read, written, or merged, and must make `is_standardized()` return `False`.

`is_standardized()` is strict, warning-free, and must not mutate its input. Tests must require exact column order, `float64` dtypes, first finite time zero, non-decreasing finite time, and no infinity. Retained `NaN` values are allowed when finite time exists. Canonical-name `float32` data or a nonzero first finite time must return `False`.

`write()` may convert compatible numeric dtypes to `float64`, but must not offset time, repair column order, discard rows, or mutate the source DataFrame. Tests must verify successful dtype conversion and rejection of inputs requiring those other changes.

---

# 4. Unit-conversion tests

The following shall be tested independently.

## Time

```text
ms → s
min → s
h → s
```

## Current

```text
A → mA
µA → mA
nA → mA
```

## Voltage

```text
mV → V
µV → V
```

## Capacity

```text
Ah → mAh
C → mAh
µAh → mAh
```

Conversions shall use explicit expected numerical values.

Tests must preserve SI prefix case: supported `mA` and `ms` must convert correctly, while unsupported `MA` and `Ms` must not silently become those units. An explicit compatible unit override may resolve unsupported source notation.

---

# 5. Time normalization tests

Tests shall verify:

```text
source: 100, 101, 102
output:   0,   1,   2
```

They shall also verify:

- duplicate timestamps retained;
- decreasing timestamps rejected;
- missing timestamps warned or rejected where required;
- absolute timestamps converted correctly when supported.

Leading and trailing `NaN` timestamps must remain in their original rows. The first finite source time defines the origin, even when it occurs after leading missing values. Non-monotonicity checks must compare finite times across missing rows without dropping those rows.

---

# 6. Recognition positive tests

Examples shall include:

```text
Time/s               → time
Elapsed Time (s)     → time

Current (mA)         → current
I/mA                 → current

Voltage (V)          → voltage
Potential/V          → voltage

Charge Capacity      → charge_capacity
Discharge Capacity   → discharge_capacity
Capacity (mAh)       → generic_capacity
```

---

# 7. Recognition negative tests

Examples shall include:

```text
Step Time             ≠ total elapsed time
Current Range         ≠ current
Current Limit         ≠ current
Current Density       ≠ current
Voltage Limit         ≠ measured voltage
Target Voltage        ≠ measured voltage
Specific Capacity     ≠ absolute capacity
Applied Current       ≠ automatically resolved measured current
```

`Applied Current (mA)` must remain unresolved as measured current without verified vendor semantics or an explicit mapping. A fixture containing both that label and `Measured Current (mA)` must select the measured current. Separate tests must verify successful verified-vendor and explicit-mapping cases.

---

# 8. Ambiguity tests

The recognizer MUST fail when two unresolved scientific interpretations remain.

Example:

```text
Cell Voltage (V)
Reference Voltage (V)
```

without contextual information.

Expected result:

```text
AmbiguousColumnError
```

Explicit mapping must resolve the same fixture successfully.

For structurally readable sources, `inspect()` must return ambiguous or unresolved recognition states and candidate evidence without requiring successful conversion. The same unmapped ambiguous fixture must fail under `read()`. An unresolved required quantity must remain inspectable while `read()` raises its appropriate missing-column or reconstruction error.

Duplicate labels must preserve distinct source positions. A name mapping matching both duplicates must fail as ambiguous; positional mapping must select the intended column without losing its sibling.

---

# 9. Current precedence tests

If both direct current and usable capacity are present:

```text
direct current MUST be used
capacity-derived current MUST NOT replace it
```

These tests must include explicit `capacity_kind` declarations and a directly selected current column containing only `NaN`. Measured-current usability depends on established semantics, known compatible units, and numeric compatibility, not on finding finite values in a bounded sample. Missing direct values must be retained and warned rather than replaced from capacity.

Include a source whose entire inspection sample has missing direct current but later rows contain finite measured current. Selection must remain identical across sampling and chunk sizes. Valid explicit capacity options must not activate reconstruction, and an unused cumulative interval option must not displace usable direct current.

---

# 10. Current reconstruction tests

At minimum, tests shall cover:

## Signed cumulative capacity

Known `Q(t)` shall produce analytically expected `I(t)`.

Positive and negative changes in a continuous signed cumulative quantity must preserve their derivative sign. A negative change alone must not be inferred to be a reset.

## Signed incremental capacity

Known `dQ` and `dt` shall produce expected current for both supported alignments:

- `capacity_interval="previous"`: `I_i = 3600 * dQ_i / (t_i - t_{i-1})`; first current is `NaN`.
- `capacity_interval="next"`: `I_i = 3600 * dQ_i / (t_{i+1} - t_i)`; last current is `NaN`, and first current may be finite.

Tests must reject incremental reconstruction when neither authoritative reader semantics nor explicit user options establish interval alignment. Labels and capacity units alone must not supply it.

Explicit `capacity_interval` must override a reader hint. Supplying a non-`None` value when cumulative reconstruction is selected must raise `CurrentReconstructionError`.

## Charge/discharge capacity pair

The reconstruction shall produce:

```text
charge     positive
discharge  negative
```

when current is reconstructed from separate capacities.

## Endpoint samples

The first cumulative-derived or previous-aligned incremental sample shall be:

```text
NaN
```

and shall generate the expected warning.

For next-aligned incremental capacity, the final sample must be `NaN` with the expected warning. A valid first interval must produce a finite first current.

## Explicit capacity interpretation

An explicit `capacity_kind` must override inferred semantics for an explicitly selected capacity column. Tests must verify that the selected column is used rather than silently falling back to another capacity strategy, and that declarations cannot bypass unit compatibility, interval validity, or reset safety.

A non-`None` `capacity_kind` without an explicit `columns["capacity"]` mapping must fail clearly.

## Invalid intervals and resets

Tests must retain affected rows with warned `NaN` current for zero, missing, or nonfinite reconstruction intervals when safe processing remains possible. Backward time must fail. Differences must use adjacent original source rows and must never bridge a missing value.

Independently known capacity resets and decreasing cumulative charge/discharge capacities must cause reconstruction to fail with `CurrentReconstructionError`. The implementation must not unwrap resets or infer cycle boundaries. This requirement also applies to explicit semantic declarations.

Reconstruction producing no finite current over the complete logical dataset must fail with `CurrentReconstructionError`. Tests must include a single-point cumulative dataset and a dataset whose every interval is invalid. Infinity in canonical time or other canonical output remains a validation failure.

---

# 11. Unsafe capacity tests

The following must not trigger automatic reconstruction:

```text
generic Capacity (mAh)
Specific Capacity (mAh/g)
ambiguous Q column
capacity with unknown unit
```

Expected outcome:

```text
CurrentReconstructionError
```

or appropriate ambiguity/error class.

---

# 12. NaN tests

NaN rows shall not be deleted automatically.

Tests shall verify:

- preservation;
- warning emission;
- correct warning class;
- affected-column reporting;
- affected-row counts for each canonical column.

Warnings may be emitted per chunk. Tests must compare warning categories and reported affected-row totals across chunk sizes, without requiring the same number of warning events. No row may be silently omitted or counted twice because it crosses a processing boundary.

---

# 13. Merge tests

Tests shall cover:

```text
A = 0,10,20,30
B = 0,5,10,15
```

Expected merged time:

```text
0,10,20,30,40,45,50,55
```

Additional tests:

- preceding dataset with one point;
- following dataset with one point;
- both datasets with one point → failure;
- leading and trailing NaN;
- repeated final times;
- search for previous valid positive `dt`;
- more than two datasets;
- different source vendors after standardization.

An empty input collection must fail with `IncompatibleDataError`. A collection containing one valid dataset must return a canonical copy without changing its rows or inventing a bridge interval.

Bridge candidates must come from adjacent original rows whose time values are both finite. The search must never infer an interval across a `NaN` gap. Offsets must use the preceding last finite time and following first finite time while preserving missing rows.

Required gap fixture:

```text
A = 0,NaN,10,10
B = 0,5
merged = 0,NaN,10,10,15,20
```

A provides no valid positive adjacent interval; B supplies the 5-second fallback bridge. Additional tests must cover trailing and leading missing endpoints, all-`NaN` time inputs, empty inputs, and failure when neither side has a valid adjacent positive interval.

---

# 14. Standardized-input tests

The library shall correctly read its own canonical outputs.

At minimum:

```text
Parquet
CSV
TXT
```

shall be tested.

CSV, TXT, and Parquet are required v0.1 output formats. Excel export is deferred and is not an acceptance requirement.

Reference text exports must use UTF-8, a header, decimal point, and no index column. CSV must use commas and TXT tabs. Custom destination text dialects are deferred beyond v0.1.

Canonical `float32` input shall become canonical `float64`.

---

# 15. Chunk-equivalence tests

For datasets covering each reconstruction strategy and its edge cases, the following processing modes must produce numerically equivalent results:

```text
complete in-memory
chunk size 1
chunk size 10
chunk size 100
chunk size 1000
other relevant sizes
```

This is especially critical for current reconstruction.

Chunk boundaries must not introduce artificial NaN values.

Place known resets, negative signed-capacity changes, missing time/capacity values, duplicate times, and zero-duration intervals directly across boundaries. Next-aligned incremental reconstruction must preserve its lookahead across boundaries, including at chunk size 1. Test leading/trailing missing time and first/last reconstructed endpoints.

Chunked and complete reads must agree on success or failure, exception class, output values and row order, warning categories, and reported affected-row totals. The number of warning events may differ because warnings may be emitted per chunk. End-of-stream validation may fail after chunks have been yielded, but `convert()` must publish its destination only after the whole operation succeeds; failed conversion must leave no partial final output.

Late-failure tests must cover a new destination and an existing destination with `overwrite=True`. `convert()` must remove only its own temporary output, preserve an existing destination byte-for-byte, and leave a new final destination absent. Equivalent atomic-publication and cleanup checks apply to `write()` failures. Successful publication must occur only after complete validation and writing.

---

# 16. Delimited-file tests

Generic reader tests shall include:

```text
comma delimiter
semicolon delimiter
tab delimiter
whitespace delimiter
decimal point
decimal comma
UTF-8
common alternate encodings where supported
header
headerless explicit mapping
```

Tests must verify explicit `sep`, `decimal`, `encoding`, `header`, and `skiprows` options independently and in combinations that automatic detection cannot safely resolve. Explicit options must take precedence over inference. Headerless positional mappings must retain the first data row. Inspection and detection samples must not consume or omit source rows during subsequent reading.

Tests must cover reference defaults `sep=None`, `decimal=None`, `encoding=None`, `header="infer"`, and `skiprows=0`. `header=None` means headerless; integer headers count nonblank table records from zero after an explicitly skipped physical-line prefix. `skiprows` counts physical lines, including blank lines. Verify these semantics across `read()`, `iter_read()`, `inspect()`, and the source side of `convert()`.

`autodetect=False` disables semantic recognition while allowing detection of unspecified parsing structure. Invalid option values, unsupported regular-expression separators, unsupported `skiprows` lists/callables, and non-default parsing options passed to unsupported readers must raise `IncompatibleDataError`. Explicit encoding must decode strictly rather than replace undecodable bytes.

---

# 17. Malformed-data tests

Tests shall include:

- malformed numeric value;
- incomplete row;
- duplicated column name;
- unknown unit;
- wrong extension with recognizable content;
- valid extension with invalid content.

No scientifically relevant row shall be silently discarded by default.

A malformed numeric cell in a structurally valid row must be retained as `NaN` with a warning. An incomplete or otherwise structurally ambiguous row must fail when a reliable cell-to-column assignment cannot be preserved. Duplicate names must remain distinguishable by position, including with explicit mappings.

---

# 18. Bio-Logic acceptance fixture

At least one representative `.mpr` fixture and one representative `.mpt` fixture shall each be tested against independently verified expected values.

The fixture should verify:

- time;
- voltage;
- direct current where present.

A separate fixture must test current reconstruction from each Bio-Logic capacity-field interpretation used automatically by v0.1, including its interval alignment and endpoint behavior. Independently known reset evidence must cause reconstruction failure.

Expected values must be cross-checked against EC-Lab export or another independently trusted reference, rather than generated solely by the backend being tested. Record the fixture's reference and tested backend version.

---

# 19. Neware acceptance fixture

At least one representative `.nda` fixture and one representative `.ndax` fixture shall each be tested against independently verified expected values.

The fixture shall verify:

```text
time
current
voltage
```

after canonical conversion.

Record the independent reference and tested backend version for each fixture. Additional fixtures must cover each distinct backend field schema or capacity interpretation that the adapter claims to support automatically.

---

# 20. Regression policy

Every real-world parser or recognition bug SHOULD become a regression test.

Bug fixes without regression tests should be exceptional.

---

# 21. Public API tests

Tests shall cover top-level imports:

```python
from battread import read
from battread import iter_read
from battread import inspect
from battread import detect_format
from battread import merge
from battread import convert
from battread import write
from battread import is_standardized
```

Public API behavior shall be tested independently of internal implementation details.

---

# 22. Error-message tests

Critical errors should be actionable.

Tests may verify key message content for:

```text
missing current
ambiguous voltage
unknown unit
missing optional dependency
non-monotonic time
existing output file
```

Messages need not be byte-for-byte frozen during early development.

---

# 23. Optional dependency tests

CI or dedicated jobs should verify behavior both:

```text
with vendor extra installed
without vendor extra installed
```

Missing extras shall produce `MissingDependencyError` with installation guidance.

---

# 24. Performance benchmarks

Benchmarks shall exist for:

```text
CSV reading
normalization
recognition
current reconstruction
merge
Parquet writing
```

Initial development shall record baselines rather than enforce arbitrary speed targets.

---

# 25. Memory benchmarks

At least one large synthetic dataset shall be used to track peak RAM for:

```text
read
iter_read
convert to Parquet
in-memory merge
```

The benchmark should demonstrate that supported streaming workflows scale primarily with chunk size rather than total source size.

`read()` and in-memory `merge()` may scale with full output size. File-level `convert_many()` and merge-to-file workflows are deferred beyond v0.1 and are not memory-benchmark acceptance requirements.

---

# 26. Documentation acceptance

Before v0.1 is considered publishable, documentation shall explain:

- installation;
- optional vendor extras;
- `read()`;
- explicit column mapping;
- explicit units;
- explicit capacity semantics and incremental interval alignment;
- generic parser options and malformed-row behavior;
- `inspect()`;
- large-file workflows;
- merge behavior;
- Parquet recommendation;
- limitations.

---

# 27. Definition of Done — v0.1

Version 0.1 is accepted only when all of the following are true:

- canonical schema implemented;
- generic CSV/TXT reader implemented;
- automatic recognition implemented;
- explicit overrides implemented;
- unit conversions tested;
- current reconstruction safety rules implemented;
- Bio-Logic reader functional;
- Neware reader functional;
- merge implemented;
- Parquet read/write implemented;
- canonical CSV/TXT read/write implemented;
- chunked generic processing implemented;
- warnings and exceptions implemented;
- tests pass;
- type checking passes;
- linting passes;
- package builds successfully;
- documentation builds successfully;
- independently verified fixtures for `.mpr`, `.mpt`, `.nda`, and `.ndax` pass;
- no known silent scientific misinterpretation remains in supported fixtures.

---

# 28. Release-blocking failures

The following shall block a v0.1 release:

```text
silent wrong-unit conversion
silent wrong-column selection
silent row loss
chunk-dependent scientific output
incorrect merge time offset
capacity reconstruction from ambiguous semantics
vendor fixture mismatch
undocumented mandatory dependency
```

---

# 29. Acceptance philosophy

The library is ready when users can trust that a successful conversion means:

> the software knows why each canonical column was selected and how each value was transformed.
