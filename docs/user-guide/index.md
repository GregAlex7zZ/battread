# Getting started

```python
import battread

data = battread.read("experiment.csv")
battread.write(data, "standardized.parquet")
```

That is the basic workflow: read a supported source into a pandas DataFrame,
then save it as Parquet, CSV or TXT. The result contains exactly `time_s`,
`current_mA`, and `voltage_V` as float64. Time starts at zero and measured
current preserves its sign.

The runnable `examples/getting_started.ipynb` notebook uses synthetic data and
introduces reading and saving before optional inspection, mappings and merging.
Install Jupyter separately and use the Python environment containing battread.

For large files, avoid assembling the complete result:

```python
battread.convert("large.csv", "standardized.parquet", chunk_size=10_000)
```

See [large files](large-files.md) for streaming and memory, [reader guides](../readers/index.md)
for supported formats, [delimited inputs](reading-delimited.md) for explicit
parser/column options, and [writing](writing-and-conversion.md) for output rules.
[Current reconstruction](current-reconstruction.md) explains the supported
fallback when measured current is absent. The [API](../api/index.md) documents
arguments, errors and warnings.
