# 0009: Prefer the total clock in paired CSV time columns

Status: accepted.

The maintainer explicitly requested `Total Time` over `Time` in every CSV,
independent of vendor metadata. Apply this rule in the delimited CSV adapter
before explicit mappings. Match parsed, normalized labels exactly, with no fuzzy
matching. Preserve declared source units. For a bare paired `Total Time`, the
public convention is seconds, including elapsed `HH:MM:SS[.fraction]` strings.
Unknown or incompatible explicit units fail.

This is a deliberate documented preference, replacing the earlier requirement
for a complete Neware export signature in this paired-clock case. It is not
value-based inference and does not change the canonical schema or measured data.
Only the paired `Time` candidate is superseded; duplicate total clocks and other
competing measured clocks still raise ambiguity. Explicit `columns`/`units`
overrides remain authoritative, and disabling autodetection disables this rule.
Generic TXT and binary reader behavior is unchanged.

The GUI may resolve remaining ambiguities through positional mappings and
explicit units using the existing public API. It pauses before emitting rows
from that source, retains previously saved separate outputs and rejects source
changes while awaiting a choice. Selection alone does not establish capacity
counter semantics or justify unsupported reconstruction.
