# ADR 0005: Typed pandas boundary for supported dependency versions

Date: 2026-10-05. Status: accepted.

## Context

All runtime tests passed with the minimum dependencies, but strict Pyright
reported incomplete pandas/NumPy signatures and unparameterized arrays.
Changing to older pandas stubs increased the diagnostics. Disabling strict
checking globally would conceal application errors and would not explain the
scientific assumptions at numeric boundaries.

## Decision

Keep strict checking enabled. Parameterize internal arrays as float64 and intp.
Use the private `_pandas.py` module to describe only the pandas interfaces
actually consumed by battread, through local structural protocols. Its helpers
delegate to the existing `to_numpy` and `to_numeric(errors="coerce")` calls,
preserving arguments, conversion behavior, missing cells and copy policy.
Generic exported arrays are refined by callers after the existing validation.

Missing-value counts are computed once and filtered by their count instead of
calling a second boolean reduction. Tests reduce boolean Series with Python
any/all and assert numeric NaNs with a typed math predicate. The random fixture
keeps its generator, seed and integer range, with a narrowly typed call.

## Consequences

Public APIs and scientific calculations remain unchanged. There is no alternate
parser and no global diagnostic suppression. Future pandas interfaces must be
added to the private boundary only when they are genuinely needed and verified.
The full installed-wheel matrix and strict type checks must pass on both current
and minimum dependency configurations before publication.
