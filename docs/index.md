# battread

`battread` standardizes supported electrochemical cycling data into three
canonical `float64` columns:

```text
time_s
current_mA
voltage_V
```

The v0.1 implementation includes generic CSV/TXT, canonical Parquet, Bio-Logic
and supported Neware layouts. Version 0.1.0 is prepared with author, license and
repository metadata. Remote GitHub Actions and security-channel activation
remain pending. The specifications define the scientific and
public API contracts; see the [acceptance report](testing/V0_1_ACCEPTANCE_REPORT.md)
for validation evidence and release limitations.

## No warranty

The software is provided as is, without warranty, to the extent permitted by
applicable law. Users must independently verify converted measurements against
their source records before relying on results. Tests do not certify all source
formats or scientific conclusions. Warranty exclusions and liability limits
are governed by sections 15-17 of the GPL-3.0-or-later license supplied with the
project; mandatory legal obligations remain applicable.
