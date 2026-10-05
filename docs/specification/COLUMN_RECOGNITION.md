# Column Recognition Specification
## Version 0.1

**Status:** Draft  
**Specification version:** 0.1  
**Related documents:**
- Data Standardization Library — Technical Specification v0.1
- Architecture & Public API Specification v0.1

---

# 1. Purpose

This document defines the automatic column-recognition subsystem used by the Data Standardization Library.

The subsystem is responsible for identifying source columns representing:

- elapsed time;
- current;
- measured voltage;
- capacity-related quantities usable for current reconstruction.

The subsystem shall be:

- deterministic;
- transparent;
- extensible;
- vendor-aware;
- conservative when ambiguity exists;
- independently testable.

Its central rule is:

> **Search broadly, classify carefully, and never resolve scientific ambiguity by guessing.**

---

# 2. Scope

Version 0.1 shall recognize the following primary quantities:

```text
time
current
voltage
capacity
```

Capacity recognition additionally distinguishes semantic subtypes:

```text
cumulative_signed
delta_signed
charge_capacity
discharge_capacity
generic_capacity
unknown_capacity
```

The recognition architecture shall allow new quantities and semantic classes to be added in future versions without redesigning the core engine.

---

# 3. Non-goals

The recognition subsystem shall not attempt to determine:

- cycles;
- half-cycles;
- electrochemical steps;
- state of charge;
- state of health;
- C-rate;
- charge/discharge classification from current sign;
- electrode chemistry;
- active material mass;
- current density conversion;
- specific capacity conversion;
- electrochemical mechanism.

Recognition identifies source quantities.

It does not perform downstream electrochemical analysis.

---

# 4. Recognition output model

Recognition shall return structured information rather than only a source-column name.

Conceptually:

```python
ColumnMatch(
    source_column="Current (mA)",
    quantity="current",
    unit="mA",
    semantic=None,
    state="resolved",
    confidence=...,
    evidence=(
        "exact_alias",
        "compatible_unit",
    ),
)
```

The exact Python representation shall be finalized during implementation.

---

# 5. Required recognition states

Every requested quantity shall end in one of the following states:

```text
explicit
resolved
ambiguous
unresolved
```

## 5.1 `explicit`

The mapping was supplied directly by the user.

## 5.2 `resolved`

The system found one sufficiently supported interpretation.

## 5.3 `ambiguous`

Multiple scientifically plausible interpretations remain.

## 5.4 `unresolved`

No acceptable candidate was found.

---

# 6. Recognition pipeline

Column recognition shall conceptually follow:

```text
raw source columns
        │
        ▼
source-column extraction
        │
        ▼
label normalization
        │
        ▼
unit extraction
        │
        ▼
candidate generation
        │
        ▼
vendor-specific evidence
        │
        ▼
generic semantic evidence
        │
        ▼
negative evidence
        │
        ▼
optional data validation
        │
        ▼
candidate ranking
        │
        ▼
ambiguity resolution
        │
        ▼
ColumnMatch result
```

These stages should remain logically separable even when optimized internally.

---

# 7. Explicit mappings have highest priority

User-provided column mappings are authoritative.

Example:

```python
read(
    "file.csv",
    columns={
        "time": "Elapsed",
        "current": "I cell",
        "voltage": "U",
    },
)
```

or:

```python
read(
    "file.txt",
    columns={
        "time": 0,
        "current": 3,
        "voltage": 7,
    },
)
```

Automatic recognition MUST NOT replace an explicit mapping.

Explicit mappings shall still be validated for basic compatibility where possible.

For example, explicitly assigning a non-numeric text column as current should produce an error rather than silently continuing.

A non-`None` `capacity_kind` requires an explicit `columns["capacity"]` mapping and overrides that column's inferred semantic subtype. This declaration cannot replace usable direct current or bypass unit compatibility, interval validity, or reset safety checks.

The supported declarations are `"cumulative_signed"` and `"delta_signed"`. Separate charge/discharge capacities use their own `columns["charge_capacity"]` and `columns["discharge_capacity"]` mappings.

For `delta_signed`, interval alignment must also be established through authoritative reader semantics or an explicit `capacity_interval="previous"` or `capacity_interval="next"` declaration. A semantic subtype alone does not establish alignment.

Explicit interval alignment takes precedence over a reader hint. `capacity_interval` applies only to incremental capacity; supplying a non-`None` value when cumulative reconstruction is selected MUST raise `CurrentReconstructionError`. Unused capacity options MUST NOT cause the implementation to reconstruct current when usable direct current is present.

---

# 8. Partial explicit mappings

Mappings may be partial.

Example:

```python
columns={
    "current": "Cell Current",
}
```

In this case:

```text
current  → explicit
time     → automatic recognition
voltage  → automatic recognition
```

The same principle applies to explicit units.

---

# 9. Column identifiers

The recognition system shall internally preserve both:

- source-column identity;
- normalized semantic representation.

A source column may be identified by:

```text
column name
column position
reader-specific field identifier
```

Binary proprietary readers may supply semantic field identifiers not visible as human-readable headers.

Such identifiers may provide stronger evidence than textual recognition.

---

# 10. Label normalization

Raw labels shall be normalized before alias matching.

Normalization should include, where appropriate:

1. Unicode normalization;
2. case folding;
3. leading/trailing whitespace removal;
4. repeated whitespace collapsing;
5. punctuation normalization;
6. bracket normalization;
7. slash normalization;
8. micro-symbol normalization;
9. separation of quantity and unit;
10. preservation of scientifically meaningful symbols.

For example:

```text
" Current (mA) "
"CURRENT[mA]"
"current / mA"
```

may normalize to comparable representations.

---

# 11. Unicode normalization

Equivalent Unicode representations shall be treated consistently.

For recognition purposes:

```text
µ
μ
u
```

may be recognized as equivalent micro-prefix representations when occurring in unit contexts.

This equivalence MUST NOT be applied blindly to arbitrary text.

---

# 12. Case normalization

Matching shall generally be case-insensitive.

Examples:

```text
CURRENT
Current
current
```

shall be equivalent for ordinary aliases.

Case MAY remain available as weak contextual information where a scientific symbol has a conventional case-sensitive meaning.

Unit symbols and SI prefixes must retain their case during extraction and lookup. Quantity-label case folding MUST NOT turn an unsupported `MA` into `mA`, or `Ms` into `ms`. Only explicitly registered unit spellings may be accepted; unsupported symbols require an error or an explicit compatible unit override.

---

# 13. Punctuation normalization

Common separators shall be normalized for matching:

```text
/
-
_
.
:
;
()
[]
{}
```

Scientific unit expressions shall first be extracted before destructive punctuation normalization.

For example:

```text
dq/mA.h
```

must not lose the information that `mA.h` represents a capacity unit.

---

# 14. Tokenization

Normalized labels SHOULD also be represented as semantic tokens.

Example:

```text
"Cell Current (mA)"
```

may produce conceptually:

```text
["cell", "current"]
```

plus:

```text
unit = "mA"
```

This enables recognition beyond exact string matching.

---

# 15. Unit extraction

Unit recognition shall occur independently from quantity recognition.

Supported unit locations include:

```text
Current (mA)
Current [mA]
Current/mA
Current mA
I/mA
Capacity(Ah)
Time/s
```

The parser shall first attempt to separate:

```text
quantity label
unit expression
```

before semantic matching.

---

# 16. Unit normalization

Equivalent unit spellings shall normalize to canonical internal forms.

Examples:

```text
mA
mamp
milliampere
milliamperes
```

may normalize to:

```text
mA
```

when support is explicitly defined.

Similarly:

```text
sec
second
seconds
```

may normalize to:

```text
s
```

---

# 17. Supported time units

Initial supported time-unit aliases SHOULD include:

```text
s
sec
secs
second
seconds

ms
msec
millisecond
milliseconds

us
µs
μs
microsecond
microseconds

min
mins
minute
minutes

h
hr
hrs
hour
hours

day
days
d
```

Ambiguous abbreviations shall be accepted only where context is sufficiently strong.

---

# 18. Supported current units

Initial supported current-unit aliases SHOULD include:

```text
A
amp
amps
ampere
amperes

mA
mamp
milliamps
milliampere
milliamperes

uA
µA
μA
microamp
microampere

nA
nanoamp
nanoampere
```

---

# 19. Supported voltage units

Initial supported voltage-unit aliases SHOULD include:

```text
V
volt
volts

mV
millivolt
millivolts

uV
µV
μV
microvolt
microvolts
```

---

# 20. Supported capacity units

Initial supported capacity units SHOULD include:

```text
Ah
A.h
A h
ampere-hour
ampere hour

mAh
mA.h
mA h
milliampere-hour

uAh
µAh
μAh

C
coulomb
coulombs
```

Where appropriate:

```text
1 Ah = 3600 C
1 mAh = 3.6 C
```

shall be used for conversion.

---

# 21. Units that must not be mistaken for canonical capacity

The recognizer shall distinguish ordinary capacity from normalized or derived quantities such as:

```text
mAh/g
Ah/kg
mAh/cm²
mAh/cm2
C/g
```

These represent specific or areal quantities and MUST NOT automatically be used for reconstructing absolute current.

Likewise:

```text
mA/cm²
A/m²
```

represent current density and MUST NOT automatically be interpreted as canonical current.

---

# 22. Alias registry

Recognition aliases shall be stored in a declarative registry wherever practical.

The registry shall separate:

```text
generic aliases
vendor-specific aliases
negative aliases
semantic capacity aliases
unit aliases
```

A conceptual layout is:

```text
aliases/
├── generic/
│   ├── time
│   ├── current
│   ├── voltage
│   └── capacity
│
├── biologic/
└── neware/
```

The storage format should be human-readable.

---

# 23. Alias registry requirements

An alias entry SHOULD be capable of specifying:

```text
target quantity
semantic subtype
exact aliases
token requirements
regular-expression patterns
compatible units
incompatible units
negative terms
vendor restriction
priority/evidence class
```

Adding an ordinary alias SHOULD NOT require modification of the central recognition algorithm.

---

# 24. Recognition evidence hierarchy

Recognition shall use a hierarchy of evidence rather than relying entirely on one opaque numerical score.

From strongest to weakest:

```text
1. explicit user mapping
2. authoritative reader-provided semantics
3. exact canonical name
4. exact known vendor alias
5. exact known generic alias
6. strong structured alias pattern
7. semantic token match
8. compatible-unit evidence
9. numerical-behavior validation
10. positional or weak contextual evidence
```

Lower-level evidence may support or reject a candidate.

Lower-level evidence SHOULD NOT override contradictory stronger evidence without explicit rules.

---

# 25. Authoritative reader evidence

A specialized reader may directly identify a source field.

For example, a known Bio-Logic binary field identifier may establish:

```text
quantity = current
unit = mA
```

without relying on string matching.

Such information shall normally take precedence over generic header heuristics.

---

# 26. Canonical names

Exact canonical names represent high-confidence evidence:

```text
time_s
current_mA
voltage_V
```

A dataset containing exactly these columns shall normally be recognized as already standardized.

---

# 27. Fuzzy matching

Approximate string matching SHALL NOT automatically resolve required scientific columns in v0.1.

A spelling such as:

```text
currnt
```

MAY generate a suggestion:

```text
Did you mean "current"?
```

but SHALL NOT automatically be classified solely because of fuzzy similarity.

This prevents typographical similarity from becoming silent scientific interpretation.

---

# 28. Machine-learning recognition

Machine-learning or language-model-based column classification is outside v0.1.

Recognition shall remain deterministic and explainable.

A future optional classifier MAY assist candidate suggestions but shall not become an opaque mandatory dependency.

---

# 29. Time recognition

The target time quantity is:

> Total elapsed experiment time.

The preferred source represents elapsed time across the complete logical acquisition.

---

# 30. Initial time aliases

Generic time aliases SHOULD include forms related to:

```text
time
elapsed time
elapsed
test time
total time
experiment time
measurement time
time elapsed
runtime
run time
t
```

plus equivalent unit-bearing forms such as:

```text
time/s
time(s)
time [s]
elapsed time (s)
```

---

# 31. Time negative evidence

The following concepts SHOULD NOT be automatically selected as canonical elapsed time when an overall time column is available:

```text
step time
cycle time
half-cycle time
segment time
phase time
pulse time
rest time
charge time
discharge time
```

These quantities may reset repeatedly and therefore do not represent total elapsed time.

---

# 32. Absolute timestamps

Columns such as:

```text
timestamp
date time
datetime
date/time
absolute time
```

may be recognized as absolute-time candidates.

They MAY be converted to elapsed time if parsing is reliable.

If both an explicit elapsed-time column and an absolute timestamp are available, elapsed time SHOULD normally be preferred.

---

# 33. Multiple time candidates

If a file contains:

```text
Test Time
Step Time
Cycle Time
```

`Test Time` shall normally win due to semantic evidence.

If multiple plausible total-time columns remain with no clear preference, recognition MUST become ambiguous.

---

# 34. Current recognition

The target current quantity is:

> Total measured electrical current associated with the electrochemical record.

---

# 35. Initial current aliases

Generic aliases SHOULD include:

```text
current
cell current
measured current
current measured
I
Icell
I cell
ampere
amps
```

and unit-bearing variants such as:

```text
I/mA
I/A
Current(A)
Current(mA)
Current [mA]
```

Vendor-specific aliases shall extend this list.

---

# 36. Current negative evidence

The following concepts MUST NOT ordinarily be selected as measured current:

```text
current range
current limit
current setpoint
current target
control current
programmed current
current density
specific current
compliance current
maximum current
minimum current
current upper limit
current lower limit
```

A vendor-specific reader MAY override this where a known label uses unusual terminology.

`Applied Current` is not a strong generic measured-current alias: it may describe a measurement or a commanded value. Without verified vendor semantics or explicit user mapping, it shall remain unresolved as measured current, even when paired with compatible units.

---

# 37. Current-density exclusion

Columns with units such as:

```text
mA/cm²
A/m²
A/g
mA/g
```

shall not be treated as absolute current.

Conversion would require additional information that is outside the standardization dataset.

---

# 38. Direct current preference

Any valid directly measured current candidate takes precedence over capacity-derived current reconstruction.

Capacity recognition is therefore a fallback mechanism, not an alternative estimate when current already exists.

Usability is established by measurement semantics, a known compatible unit, and numeric compatibility. It MUST NOT depend on how many finite values occur in an inspection sample. Even an all-`NaN` directly selected current column is retained and warned; capacity reconstruction MUST NOT replace it.

---

# 39. Voltage recognition

The target voltage quantity is:

> The measured electrochemical potential or cell voltage required for downstream cycling analysis.

---

# 40. Initial voltage aliases

Generic aliases SHOULD include:

```text
voltage
cell voltage
measured voltage
potential
cell potential
E
U
V
```

where ambiguity can be resolved safely.

Vendor-specific examples may include:

```text
Ewe
Ewe/V
Ecell
Ecell/V
```

when their semantics are known.

---

# 41. Voltage negative evidence

Columns representing the following SHOULD NOT be preferred as measured voltage:

```text
voltage limit
upper voltage
lower voltage
voltage setpoint
target voltage
control voltage
programmed voltage
voltage range
cutoff voltage
voltage compliance
```

---

# 42. Multiple measured voltages

A generic file may contain multiple scientifically legitimate measured potentials.

For example:

```text
working electrode voltage
counter electrode voltage
reference potential
cell voltage
```

If the appropriate canonical quantity cannot be determined safely, recognition MUST return ambiguity.

The library MUST NOT choose based solely on column order.

Vendor-specific readers MAY establish a preferred canonical potential where the instrument format defines the semantics clearly.

---

# 43. Capacity recognition

Capacity recognition is more conservative than current or voltage recognition because similar-looking columns may represent fundamentally different quantities.

The recognizer shall first determine:

```text
Is this capacity-like?
```

and separately:

```text
What capacity semantics does it have?
```

---

# 44. Capacity semantic classes

Recognized capacity candidates shall, where possible, be classified as:

```text
cumulative_signed
delta_signed
charge_capacity
discharge_capacity
generic_capacity
unknown_capacity
```

---

# 45. Generic capacity aliases

Initial generic capacity-like aliases SHOULD include:

```text
capacity
cap
Q
charge
capacity passed
charge passed
```

These aliases establish only that a quantity MAY be capacity-like.

They do not automatically establish its semantic subtype.

---

# 46. Charge-capacity aliases

Strong charge-capacity aliases SHOULD include forms related to:

```text
charge capacity
charging capacity
chg capacity
chg cap
Q charge
Qcharge
charge cap
capacity charge
```

with supported capacity units.

---

# 47. Discharge-capacity aliases

Strong discharge-capacity aliases SHOULD include forms related to:

```text
discharge capacity
discharging capacity
dchg capacity
dchg cap
DChg capacity
Q discharge
Qdischarge
discharge cap
capacity discharge
```

---

# 48. Delta-capacity aliases

Strong incremental/delta-capacity evidence includes terms such as:

```text
dq
dQ
delta Q
delta capacity
capacity increment
incremental capacity
charge increment
```

Vendor-specific definitions may further determine whether the quantity is signed and how it aligns with the time interval.

---

# 49. Specific-capacity exclusion

Columns such as:

```text
specific capacity
charge capacity (mAh/g)
discharge capacity (mAh/g)
capacity / mass
gravimetric capacity
areal capacity
volumetric capacity
```

shall not automatically be used for current reconstruction.

They require additional normalization information such as active mass, area, or volume.

---

# 50. Capacity unit compatibility

Capacity candidates shall require compatible charge units before automatic current reconstruction.

Examples of valid absolute capacity units:

```text
Ah
mAh
µAh
C
```

Examples of non-equivalent derived quantities:

```text
mAh/g
mAh/cm²
Ah/L
```

---

# 51. `cumulative_signed`

A capacity candidate may be classified as `cumulative_signed` when reliable semantic evidence establishes that:

- it is cumulative;
- it is signed;
- changes in the quantity correspond to signed transferred charge.

The cumulative quantity must be continuous across the logical acquisition. An explicit `capacity_kind="cumulative_signed"` declaration asserts this continuity as well as signed semantics.

Reconstruction uses the difference between the current row and the immediately preceding source row. The first sample is `NaN`. Neither a missing row nor a processing chunk boundary permits a different alignment or a difference spanning missing values.

Numerical behavior MAY confirm this classification.

Numerical behavior alone MUST NOT establish it.

---

# 52. `delta_signed`

A candidate may be classified as `delta_signed` when reliable evidence establishes that each value represents signed transferred charge over a sampling interval.

Labels such as:

```text
dq
dQ
```

provide strong evidence only when their source semantics are known sufficiently.

Automatic reconstruction requires authoritative reader evidence for interval alignment, or the user must declare `capacity_interval` explicitly:

| Alignment | Meaning of `dQ_i` | Current in mA when capacity is in mAh | Unavailable endpoint |
|---|---|---|---|
| `previous` | Charge transferred from row `i-1` to row `i` | `3600 * dQ_i / (t_i - t_{i-1})` | First sample is `NaN` |
| `next` | Charge transferred from row `i` to row `i+1` | `3600 * dQ_i / (t_{i+1} - t_i)` | Last sample is `NaN`; first may be finite |

Both rows defining an interval must be adjacent original source rows with finite times and a positive time difference. Missing intervals MUST NOT be bridged. Next-aligned processing must preserve lookahead across chunk boundaries. Generic recognition MUST NOT assume either alignment from a label such as `dq` alone.

Zero or missing local intervals produce retained rows with `NaN` reconstructed current and a warning. Invalid computed intervals may be handled the same way when safe, but backward finite time MUST raise `NonMonotonicTimeError`, and infinity in canonical quantities MUST fail validation. Reconstruction MUST fail if the complete logical dataset contains no finite reconstructed current; this includes a single-point cumulative-capacity dataset.

---

# 53. Separate charge/discharge capacity pair

When both:

```text
charge_capacity
discharge_capacity
```

are confidently identified, they shall not be treated as ambiguous competing versions of the same column.

Instead they form a valid semantic pair potentially usable for current reconstruction.

---

# 54. Ambiguous generic capacity

A source such as:

```text
Capacity (mAh)
```

shall generally be recognized as:

```text
quantity = capacity
semantic = generic_capacity
```

unless vendor-specific or other strong evidence establishes more precise semantics.

It MUST NOT automatically be differentiated to obtain current.

---

# 55. Numerical behavior as validation

Bounded numerical sampling MAY be used to validate a proposed match.

Examples include checking whether:

```text
time is numeric or parseable
capacity is numeric
voltage values are finite
charge capacity is broadly cumulative
```

Behavior is supporting evidence.

It shall not replace semantic evidence.

---

# 56. Numerical magnitude

Typical numerical magnitude MAY be used to reject clearly impossible interpretations but SHOULD NOT normally establish quantity identity.

For example:

```text
3.7
3.8
3.6
```

looks plausible as battery voltage but could represent another quantity.

Magnitude alone is insufficient for automatic voltage selection.

---

# 57. Monotonic behavior

Monotonic increase MAY support classification of cumulative capacity.

However:

```text
monotonic → cumulative capacity
```

is not a valid standalone inference.

Many unrelated experimental variables may also be monotonic.

---

# 58. Capacity resets

Known resets in capacity information selected for reconstruction MUST cause reconstruction to fail in v0.1. Decreasing values in a selected cumulative charge-capacity or discharge-capacity field likewise invalidate reconstruction. The implementation MUST NOT unwrap resets or reinterpret them as acquisition boundaries.

A negative change in a continuous `cumulative_signed` quantity is legitimate signed transferred charge. It MUST NOT be classified as a reset solely because it is negative. An explicit cumulative-signed declaration asserts continuity; independently known reset evidence still requires failure.

The recognition engine SHALL NOT automatically infer:

```text
capacity reset = cycle boundary
```

Cycle interpretation belongs downstream.

---

# 59. Missing values during recognition

A candidate column containing some missing values shall not automatically be rejected.

Recognition MAY evaluate finite samples.

Missing-value reporting belongs to final validation.

---

# 60. Constant columns

A constant column may still represent a legitimate measurement during part of an experiment.

Constant numerical behavior alone SHALL NOT disqualify current or voltage.

For example, a constant current experiment legitimately contains nearly constant current.

---

# 61. Candidate generation

Each source column MAY generate zero, one, or several quantity candidates.

For example:

```text
"Capacity (mAh)"
```

may initially generate:

```text
capacity / generic_capacity
```

while:

```text
"Discharge Capacity (mAh)"
```

may generate:

```text
capacity / discharge_capacity
```

with stronger evidence.

---

# 62. Candidate ranking

The recognition engine shall rank candidates primarily by evidence class rather than arbitrary source-column order.

A weaker match MUST NOT defeat a stronger semantic match simply because it occurs earlier in the file.

---

# 63. Tie handling

If two candidates remain scientifically equivalent after all reliable evidence is applied, the system MUST report ambiguity.

Example:

```text
Current 1 (mA)
Current 2 (mA)
```

with no contextual information distinguishing them.

The library SHALL NOT silently select the first column.

---

# 64. Evidence margin

Implementations MAY use an internal numerical score to combine evidence.

If used:

- score constants MUST be centralized;
- thresholds MUST be covered by tests;
- source-column order MUST NOT affect scores;
- scores are implementation details;
- ambiguity must remain explicitly representable.

No public scientific meaning shall be assigned to a score such as `0.92`.

---

# 65. Recommended evidence tiers

The reference implementation SHOULD behave approximately according to the following tiers:

### Tier A — Authoritative

```text
explicit user mapping
reader-provided field semantics
```

### Tier B — Strong

```text
exact canonical name
exact vendor alias
exact semantic alias + compatible unit
```

### Tier C — Moderate

```text
exact generic alias
strong regex pattern
strong token composition
```

### Tier D — Supporting

```text
compatible unit
numerical behavior
column type
weak contextual evidence
```

### Tier X — Negative

```text
negative semantic terms
incompatible unit
derived quantity
known control/setpoint field
```

Tier D evidence alone SHOULD NOT normally resolve a required scientific quantity.

---

# 66. Negative evidence priority

Strong negative evidence shall be capable of disqualifying an otherwise superficially similar alias.

For example:

```text
"Current Limit (mA)"
```

contains both:

```text
current
mA
```

but `limit` is strong negative evidence.

It must therefore not automatically become canonical current.

---

# 67. Vendor-specific overlays

When the file format is known, vendor-specific recognition rules shall supplement generic rules.

Conceptually:

```text
generic recognition
+
Bio-Logic overlay
```

or:

```text
generic recognition
+
Neware overlay
```

Vendor overlays MAY:

- add aliases;
- assign stronger semantics;
- define field identifiers;
- specify units;
- mark known exclusions;
- define capacity semantics.

---

# 68. Vendor rules shall remain isolated

A Bio-Logic-specific rule MUST NOT alter recognition behavior for unrelated generic CSV files unless the same alias is intentionally promoted to the generic registry.

Likewise for Neware and future vendors.

---

# 69. Reader hints

Readers MAY provide structured hints before generic recognition.

Conceptually:

```python
ReaderHint(
    column="Ewe/V",
    quantity="voltage",
    unit="V",
    confidence="authoritative",
)
```

This is preferred over embedding vendor-name checks inside the generic recognition engine.

---

# 70. Canonical schema fast path

If a source contains exactly or unambiguously:

```text
time_s
current_mA
voltage_V
```

the recognizer shall use a canonical fast path.

Exact names alone do not establish valid canonical data. Empty datasets and nonempty datasets with no finite time are invalid in v0.1. Infinity is invalid in every canonical quantity; leading and trailing missing values may be retained when at least one finite time establishes the origin.

It shall:

1. validate the columns;
2. convert to `float64` if required;
3. validate time behavior;
4. bypass unnecessary alias scoring.

---

# 71. Headerless files

Automatic semantic recognition from data position alone shall not occur generically in v0.1.

Headerless files require explicit positional mapping unless a specialized reader defines a known fixed schema.

Example:

```python
columns={
    "time": 0,
    "current": 2,
    "voltage": 4,
}
```

---

# 72. Column position

Column position MAY provide supporting evidence only when a specialized known format defines meaningful positions.

For arbitrary CSV/TXT files:

> Position is not semantic evidence.

---

# 73. Duplicate column names

If the source parser produces duplicate labels:

```text
Current
Current
```

the recognition subsystem MUST preserve the ability to distinguish them by positional identity.

Duplicate names MUST NOT cause one column to be silently lost.

If both are plausible candidates, ambiguity shall be reported.

A name-based explicit mapping matching duplicate labels is itself ambiguous and MUST fail. Positional mapping is the required way to select one such column unambiguously.

---

# 74. Data sampling

Numerical validation SHOULD use a bounded sample rather than scanning an entire multi-gigabyte source solely for recognition.

The sample should be sufficiently large to detect obvious incompatibility while keeping inspection efficient.

The exact sample size is an implementation parameter.

---

# 75. Sampling invariance

Candidate semantic identity SHOULD NOT normally depend on source-file size or arbitrary chunk size.

Sampling is primarily for validation, not semantic invention.

---

# 76. Recognition explainability

Every resolved automatic match SHOULD internally preserve its principal evidence.

For example:

```text
Column: "I/mA"
Quantity: current
Reason:
- exact Bio-Logic alias
- unit mA compatible with current
```

This information may be surfaced through `inspect()`.

---

# 77. Inspection presentation

A human-readable inspection may conceptually display:

```text
Current
-------
Selected:
    I/mA

Interpretation:
    quantity: current
    unit: mA

Evidence:
    Bio-Logic alias
    compatible current unit

Rejected:
    Current Range
        reason: range/control field
```

This is particularly useful for debugging new file variants.

---

# 78. Ambiguity errors

An ambiguity error MUST identify:

- requested quantity;
- plausible candidate columns;
- any detected units;
- suggested user action.

Example:

```text
Ambiguous voltage columns detected:

1. "Cell Voltage (V)"
2. "Reference Voltage (V)"

Both represent plausible measured potentials.

Specify the desired source explicitly using:

    columns={"voltage": "..."}
```

---

# 79. Unresolved errors

If no current is found, the recognition pipeline shall continue to capacity recognition before failing.

If no voltage is found:

```text
MissingColumnError
```

shall be raised.

If no usable time is found:

```text
MissingColumnError
```

shall be raised.

---

# 80. Current fallback sequence

Recognition shall follow:

```text
direct current?
    │
  yes ───────→ use
    │
   no
    ▼
capacity candidates?
    │
   no ───────→ fail
    │
   yes
    ▼
safe capacity semantics?
    │
   no ───────→ require explicit interpretation
    │
   yes
    ▼
reconstruct current
```

---

# 81. Capacity-pair selection

If multiple capacity-related columns exist, the recognition engine shall identify compatible semantic combinations rather than simply choosing the highest-ranked individual capacity column.

For example:

```text
Charge Capacity
Discharge Capacity
```

constitutes a meaningful pair.

---

# 82. Capacity strategy priority

Usable direct current always takes precedence, including when capacity semantics have been declared explicitly.

Where direct current is absent, current-reconstruction strategies SHOULD be considered approximately in this order:

1. explicit user-declared semantics for an explicitly selected capacity column;
2. authoritative signed incremental capacity with established interval alignment;
3. authoritative signed cumulative capacity;
4. reliable charge/discharge capacity pair;
5. otherwise fail.

An explicit selection MUST NOT be silently replaced by a different capacity strategy if its safety checks fail. The exact preference between automatic strategies 2 and 3 MAY be reader-specific when both are available and equivalent.

---

# 83. Alias registry data model

A conceptual alias record may resemble:

```yaml
quantity: current

aliases:
  exact:
    - current
    - cell current
    - measured current

patterns:
  - "^i$"

units:
  allowed:
    - A
    - mA
    - uA
    - nA

negative_terms:
  - limit
  - range
  - setpoint
  - target
  - density
```

This representation is illustrative rather than a final storage-format requirement.

---

# 84. Capacity alias data model

A semantic capacity rule may conceptually resemble:

```yaml
quantity: capacity
semantic: discharge_capacity

aliases:
  exact:
    - discharge capacity
    - dchg capacity
    - dchg cap
    - q discharge

units:
  allowed:
    - Ah
    - mAh
    - uAh
    - C
```

---

# 85. Registry versioning

Alias registries SHOULD be version-controlled with the source code.

Changes to aliases MUST be tested.

Significant recognition changes SHOULD appear in the changelog.

---

# 86. Registry collisions

Adding a new alias must not silently introduce ambiguity for previously recognized fixtures.

CI SHOULD test the complete recognition fixture set after registry changes.

---

# 87. Recognition regression tests

Every reported real-world recognition bug SHOULD ideally result in a regression test.

For example:

```text
Issue:
"Current Range" incorrectly recognized as current.

Regression:
test_current_range_is_not_current()
```

This enables the registry and recognizer to improve safely over time.

---

# 88. Minimum generic recognition tests

Tests shall include at least:

```text
Time/s                  → time
Elapsed Time (s)        → time
Step Time (s)           → not preferred total time

Current (mA)            → current
I/mA                    → current
Current Range            → reject

Voltage (V)             → voltage
Potential/V              → voltage
Voltage Limit (V)       → reject/prefer measured alternative

Charge Capacity (mAh)   → charge_capacity
Discharge Capacity      → discharge_capacity
dq/mA.h                 → delta capacity candidate
Capacity (mAh)          → generic_capacity

Specific Capacity
(mAh/g)                 → non-reconstructable capacity
```

---

# 89. Multiple-candidate tests

Tests shall deliberately include ambiguity.

Example:

```text
Cell Voltage (V)
Reference Voltage (V)
```

Expected:

```text
AmbiguousColumnError
```

unless reader-specific information resolves the meaning.

---

# 90. Explicit-override tests

For every automatic ambiguity case, tests SHOULD verify that explicit mapping successfully resolves it.

---

# 91. Unit-conflict tests

Tests shall verify that incompatible units prevent false matches.

Examples:

```text
Current (V)
Voltage (mA)
Capacity (mA)
```

shall not be silently interpreted according only to quantity names.

---

# 92. Derived-quantity tests

The recognizer shall be tested against derived quantities such as:

```text
dQ/dV
dV/dQ
dV/dt
current density
specific capacity
areal capacity
```

These MUST NOT be mistaken for the canonical primitive measurements.

---

# 93. Language support

Version 0.1 may primarily target:

- English generic headers;
- vendor-specific header strings;
- standard scientific symbols.

The registry architecture shall permit aliases in additional languages.

Contributions of validated non-English aliases SHOULD be welcomed.

Language detection is not required.

---

# 94. Scientific symbols

Common scientific symbols such as:

```text
t
I
U
E
Q
dQ
dq
```

MAY participate in recognition.

Because isolated single-letter symbols are inherently ambiguous, they generally require supporting evidence such as:

- unit;
- vendor-specific context;
- reader hint.

For example:

```text
I (mA)
```

is strong evidence for current.

A column named only:

```text
I
```

without additional information is weaker evidence.

---

# 95. Single-letter aliases

Single-character aliases SHALL NOT automatically receive the same strength as descriptive exact aliases.

This applies particularly to:

```text
I
E
V
U
Q
t
```

Compatible units may elevate confidence.

---

# 96. Unitless columns

A descriptive header may still establish quantity even when no unit is embedded.

Example:

```text
Cell Current
```

may be recognized as current.

However, if the unit cannot be established from:

- reader knowledge;
- another unit row;
- source metadata;
- explicit user mapping;

automatic canonical conversion MUST NOT proceed.

The quantity may be resolved while the unit remains unresolved.

---

# 97. Multi-row headers

Generic text readers SHOULD allow the recognition layer to consume normalized headers extracted from common multi-row table structures where practical.

For example:

```text
Current | Voltage | Time
mA      | V       | s
```

may be combined conceptually into:

```text
Current (mA)
Voltage (V)
Time (s)
```

The text reader, rather than the recognizer itself, is responsible for presenting a usable column/unit representation.

---

# 98. Reader-recognition boundary

Readers are responsible for extracting source structure.

The recognition subsystem is responsible for interpreting that structure.

Conceptually:

```text
reader:
    "column 4 is called I/mA"

recognizer:
    "I/mA means current in mA"
```

A specialized reader MAY additionally provide authoritative semantics.

---

# 99. No silent fallback to arbitrary numerics

When a required column cannot be recognized, the library MUST NOT fall back to rules such as:

```text
first numeric column = time
second numeric column = voltage
third numeric column = current
```

unless the source format explicitly defines that positional schema.

---

# 100. Recognition determinism

Given identical:

- source columns;
- vendor context;
- aliases;
- explicit options;

the recognizer MUST produce identical results.

Recognition MUST NOT depend on:

- hash ordering;
- filesystem ordering;
- incidental candidate iteration order.

---

# 101. Performance

Column recognition normally operates on a small number of columns and should not be a major performance bottleneck.

The implementation SHOULD prioritize:

1. correctness;
2. explainability;
3. maintainability;

before micro-optimizing header matching.

Numerical validation on large data shall remain bounded.

---

# 102. Public customization

Version 0.1 does not require a full public custom-alias API.

The architecture SHOULD nevertheless permit future support such as:

```python
read(
    path,
    aliases=my_aliases,
)
```

without redesigning the recognition engine.

---

# 103. Internal registry immutability

Loaded default alias registries SHOULD be treated as immutable during normal processing.

Per-call customizations, if later supported, should create local overlays rather than mutate global scientific behavior.

---

# 104. Contribution documentation

Contributor documentation SHALL explain how to:

- add a current alias;
- add a voltage alias;
- add a time alias;
- add a capacity semantic alias;
- add a negative keyword;
- add a vendor-specific rule;
- write regression tests;
- diagnose ambiguity using `inspect()`.

---

# 105. Recognition success criterion

Automatic recognition is successful only when the system can establish with sufficient evidence that selected columns represent:

```text
elapsed time
measured current
measured voltage
```

or, when current is absent:

```text
capacity information with sufficiently established semantics
```

for safe current reconstruction.

Finding a numerically plausible column is not sufficient.

---

# 106. Recognition safety criterion

The core safety invariant is:

> **When two interpretations are scientifically plausible and available evidence cannot distinguish them, the correct result is ambiguity, not automation.**

---

# 107. Extensibility criterion

The recognition architecture is successful when support for a newly encountered header such as:

```text
I_cell [mA]
```

can normally be added through:

1. one registry change;
2. one or more tests;

without modifying:

- `read()`;
- reader selection;
- unit-conversion algorithms;
- candidate-resolution architecture.

---

# 108. Guiding principle

The recognition engine shall aim to be:

> **Broad in what it understands, strict in what it accepts, and explicit about what it cannot know.**

Its purpose is not to maximize the percentage of files converted without questions.

Its purpose is to maximize the percentage of files converted **correctly**, while making unresolved cases easy for users and contributors to diagnose.
