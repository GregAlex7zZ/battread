# User guide

Battread currently reads generic CSV and TXT sources containing direct elapsed
time, measured current, and measured voltage, as well as canonical Parquet and
[Bio-Logic MPR/MPT](../readers/biologic.md) and
[Neware NDA/NDAX and CSV exports](../readers/neware.md).
It writes canonical Parquet, CSV, and TXT and can stream conversions between
supported sources and these output formats. See
[Reading delimited data](reading-delimited.md) for automatic and explicit
workflows and [Writing and conversion](writing-and-conversion.md) for canonical
outputs. See [Current reconstruction](current-reconstruction.md) for the
supported capacity semantics and required explicit declarations.

The [technical specification](../specification/TECHNICAL_SPECIFICATION.md)
remains the authoritative behavior contract.
