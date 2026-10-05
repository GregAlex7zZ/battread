# 0002: Bio-Logic adapter and capacity boundaries

Status: accepted for Milestone 7.

The dq restriction below is superseded by
[ADR 0003](0003-biologic-dq-preference.md), following the user's clarification
and independent interval-charge acceptance tests.

## Decision

Use Galvani 0.5.0 only for MPR binary decoding, imported lazily inside the
Bio-Logic module. Use native record streaming for MPT so missing numeric cells
can be retained and malformed scientific record widths fail explicitly.
Galvani's MPT NumPy loader does not provide that recovery policy or streaming.

Share the existing table standardization machinery with both adapters. Vendor
readers supply source columns, records, and authoritative measurement hints;
unit conversion, direct-current precedence, conservative reconstruction,
time normalization, and validation use the existing implementation. No vendor
backend type escapes into the public API or generic core.

Recognize duplicate binary fields even when Galvani adds ordinal suffixes.
No such suffix is evidence for selecting one scientific measurement.

Recognize explicit charge/discharge pairs as cumulative capacities and reject
decreases, including decreases across missing rows and chunk boundaries.
Do not automatically assign signedness, continuity, or alignment to `dq` or
`(Q-Qo)` from names alone. Techniques and recording conventions vary, and the
available reference does not establish a universal safe interpretation.
Explicit scientific declarations remain available under the common contract.

## Evidence and consequences

The real BT-Lab export includes terminal header padding and capacity resets.
Both are regression-tested against the independently parsed export.
MPT streams; MPR loads in full because Galvani materializes the complete table.
MPR inspection has the same memory limitation. Atomic conversion still waits
for complete validation before publishing output.

Only the pair interpretation is claimed as automatic Bio-Logic reconstruction
in v0.1. Adding another interpretation requires its own independent reference,
reset-safety evidence, and interval/endpoint regression tests.
