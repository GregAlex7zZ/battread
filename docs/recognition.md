# Column recognition

Battread's recognition core classifies source headers before a reader converts
their values. It normalizes labels, extracts registered units, applies generic
aliases plus an optional vendor overlay, and records the evidence for every
source position. Duplicate labels therefore remain distinct.

Recognition is conservative. Descriptive aliases can resolve a quantity, while
single-letter symbols need a compatible unit. Unit evidence alone does not
select a scientific quantity. Control fields, limits, setpoints, density fields,
specific capacity, and derived units are rejected even when their labels contain
words such as `current`, `voltage`, or `capacity`. Tied plausible measurements
remain ambiguous.

Capacity classification is separate from permission to reconstruct current.
Generic capacity and generic `dq` labels do not establish signedness or interval
alignment. A specialized reader must provide authoritative semantics, or the
user must provide explicit options through a reader API.

`ColumnMatch` records the source label and zero-based position, quantity, unit,
capacity semantic, interval alignment, state, confidence, and evidence. The
public decision is its `resolved`, `ambiguous`, `unresolved`, or `explicit`
state; confidence is an internal ranking value rather than scientific truth.
