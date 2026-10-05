# Current reconstruction

Measured current always takes precedence, including when its values are missing.
When current is absent, capacity can supply current only with established
scientific semantics and compatible units.

For a continuous signed cumulative capacity, declare the interpretation:

```python
from battread import read

data = read(
    "capacity.csv",
    columns={"capacity": "Capacity (mAh)"},
    capacity_kind="cumulative_signed",
)
```

Current is `3600 * (Q[i] - Q[i-1]) / (t[i] - t[i-1])` with capacity in mAh
and time in seconds. Negative changes retain their discharge sign. The first
current is missing because no preceding interval exists.

For signed interval capacity, use `capacity_kind="delta_signed"` and declare
`capacity_interval="previous"` or `"next"`. Previous alignment uses the interval
ending at the row and leaves the first current missing. Next alignment uses the
interval starting at the row and leaves the last current missing. Cumulative
capacity does not accept interval alignment.

A reliably recognized cumulative charge/discharge pair uses
`3600 * (delta_charge - delta_discharge) / delta_time`. Both capacities must
remain non-decreasing. Known resets raise `CurrentReconstructionError`, including
when an explicit declaration selects a known charge or discharge capacity.
Generic, single-sided, specific, or ambiguous capacity is never interpreted
automatically as continuous signed charge transfer.

Every interval uses adjacent original rows. Missing time or capacity and zero
duration leave affected current values missing with `MissingValueWarning`;
rows are retained. Backwards time fails. A source that produces no finite
reconstructed current raises `CurrentReconstructionError`.

`iter_read()` preserves interval state across chunks. Next alignment retains
one row of lookahead. Exhaust the iterator to complete validation; `convert()`
publishes output only after that validation succeeds.
