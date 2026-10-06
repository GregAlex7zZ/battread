# 0004: Strict Neware records and recorded timestamps

Status: accepted.

The audited NewareNDA 2026.6.11 high-level functions sort or deduplicate NDA
measurements and interpolate split NDAX timestamps. These operations conflict
with the canonical ingestion contract. Use isolated low-level decoders for
full records and structural block decoding for split records; pin the backend
until newer versions pass the adapter regressions.

Use recorded timestamps rather than resetting step clocks. Preserve missing
timestamps and duplicate finite times. Reject conflicting timestamp checkpoints
and unknown record framing rather than selecting or dropping them. Sparse
metadata cannot justify interpolated scientific time. Trailing all-zero split
primary slots beyond the final nonzero slot and checkpoint are reserved padding;
interior zero slots remain measurements. Unknown layouts fail explicitly.

This reduces automatic compatibility with some files accepted by the backend,
but keeps scientific transformations reviewable. Additional layouts require
documented framing and regression fixtures before acceptance.
