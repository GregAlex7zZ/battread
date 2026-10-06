# battread

Standardize electrochemical cycling data into `time_s`, `current_mA`, and
`voltage_V`: three float64 columns in a pandas DataFrame.

```python
import battread

data = battread.read("experiment.csv")
battread.write(data, "standardized.parquet")
```

Begin with [usage](user-guide/index.md), then consult the [API](api/index.md)
and [reader guides](readers/index.md). For large acquisitions, use
[streaming conversion](user-guide/large-files.md) rather than collecting a
complete DataFrame. The example notebook in `examples/getting_started.ipynb`
provides a runnable introduction with synthetic data.

## No warranty

Provided as is, without warranty, under GPL-3.0-or-later. Independently verify
converted measurements before relying on scientific results. The license's
warranty exclusions and liability limits apply subject to applicable law.
