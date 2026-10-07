# Neware

The current maintainer workflow uses CSV autoexports. NDA/NDAX adapters are
experimental, with limited real-fixture coverage and synthetic tests for some
layouts. Wider validation against complete acquisitions and manufacturer
exports is deferred to future versions, tracked in the root `TODO.md` checklist.
Existing tests and conservative error behavior remain in place.

Neware CSV exports use the generic streaming reader without an optional backend.
CSV exports containing both Time and Total Time select Total Time automatically,
using the general CSV policy. Step Type can be missing or unnamed; a vendor
signature is not needed for this paired-clock preference. Explicit units are
respected; bare paired Total Time means seconds. The rejected step clock and
selected total clock are explained in `inspect()`. Clock values become elapsed
float64 seconds starting at zero. Explicit mappings retain precedence, while
duplicate total clocks and unrelated ambiguities still require a choice.

Install `pip install "battread[neware]"` for NDA and NDAX support.
The isolated adapter uses NewareNDA 2026.6.11 (BSD-3-Clause) record decoders.
The audited version is pinned because its low-level interfaces are private.

NDA layouts 29 and 130 (88-byte BTS9 and 56-byte BTS9.1 records), full NDC
layouts 2 and 5, and split NDC layouts 11, 14, 16 and 17 are recognized.
Other layouts and unknown framing fail explicitly. Support is limited to
these profiles; recognition of a version does not guarantee every hardware
variant is compatible.

Both readers stream measurements. Split NDAX first scans the primary stream
and retains a timestamp checkpoint dictionary, so memory grows with checkpoint
count. It performs a second primary pass to distinguish trailing reserved
zero padding from measurements. Interior zero voltage/current rows are kept.
Split-NDAX inspection also scans primary blocks and timestamp metadata to
validate this profile; it is not a bounded text-header inspection.

Canonical time uses recorded timestamps, because the vendor's `Time` is a
step clock that resets. Second-resolution timestamps remain second-resolution;
duplicate times are preserved. Sparse timestamps remain NaN with a warning.
Conflicting checkpoints for one measurement index fail. No interpolation,
sorting, scientific row deduplication, or cycle analysis is performed.
Measured current retains its sign. Capacity reconstruction is not inferred
from Neware's step-dependent capacity fields.

The adapter intentionally bypasses the backend's high-level postprocessing.
See [the decision record](../adr/0004-neware-strict-records.md).
