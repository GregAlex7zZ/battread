# 0003: Prefer verified Bio-Logic dq when measured current is absent

Status: accepted.

## Decision

Measured current always takes precedence, including missing measured values.
When it is absent, prefer Bio-Logic `dq/mA.h`, `dQ/mA.h`, or `dQ/C` as signed
incremental charge ending at the recorded row. Use the preceding adjacent
original time interval, leaving the first reconstructed current missing.
Convert coulombs to mAh through the existing unit system.

Apply these interpretations as authoritative vendor reader hints. Generic
label recognition remains conservative. `(Q-Qo)` remains unresolved without an
explicit scientific declaration. The signed incremental strategy precedes a
separate charge/discharge pair when both are available. Explicit source and
semantic selections, including interval alignment, remain authoritative.
Multiple dq candidates fail with ambiguity; invalid selected dq does not
silently activate another strategy.

## Evidence

The independent BT-Lab ASCII export in the attributed acceptance fixture
contains positive and negative dq values. Previous-aligned interval current
agrees closely with the exported measured current in constant-current regions;
it is an interval average and need not equal an instantaneous endpoint current.

Acceptance tests remove direct current from this independent export and compute
the reference with its original timestamps and dq values. They check both signs,
the missing first sample, and equivalence across chunk sizes including one.
Binary tests construct a declared MPR layout from the same exported values;
Galvani does not generate expected results. Full export tests retain cumulative
capacity resets and establish that those unused capacities do not displace dq.
Additional tests cover coulomb conversion, explicit overrides, duplicated dq,
and preservation of an all-missing measured-current column.

No cumulative resets are repaired or unwrapped. Incremental dq is used directly
as interval charge, so resets of unrelated accumulated capacity are not evidence
of a reset in the selected incremental field.
