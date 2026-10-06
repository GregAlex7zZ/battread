# Understanding and documenting the code

The library separates format decoding from scientific decisions. A reader
understands its container; recognition identifies supported columns;
normalization converts established units and time; validation checks the
canonical contract. Keeping these steps separate makes a failure explainable
and keeps vendor dependencies out of generic processing.

## Suggested reading order

1. `src/battread/__init__.py` exposes the public API. Start with the docstrings
   of `read`, `inspect`, `iter_read`, `merge`, `write` and `convert`.
2. `constants.py`, `exceptions.py`, `warnings.py` and `validation.py` define the
   shared schema, failures and data-quality reporting.
3. `api.py` validates user options and selects an adapter through
   `readers/registry.py`. `readers/base.py` defines the adapter contract;
   `readers/models.py` explains its configuration and capabilities.
4. `recognition/labels.py` parses labels without fuzzy matching.
   `recognition/registry.py` contains declarative evidence; `engine.py` applies
   it and detects ambiguity. `models.py` describes the resulting explanations.
5. `normalization/units.py` preserves SI prefix case and conversion scale;
   `normalization/time.py` shifts an established time series without sorting it.
6. `readers/delimited.py` demonstrates the complete text processing path.
   Bio-Logic, Neware and Parquet adapters explain their format-specific limits.
7. `reconstruction.py` handles established capacity semantics using adjacent
   original rows. `canonical.py` maintains validation state across chunks.
8. `merge.py` joins standardized frames. `output.py` owns atomic destinations
   and streaming sinks. `benchmarks/run.py` measures observed performance.

`_pandas.py` describes the narrow pandas interfaces used by numeric conversion.
It delegates to pandas unchanged while supplying complete local types where
older upstream stubs are incomplete. Scientific validation remains with the
callers; see ADR 0005 for the reason and maintenance constraints.

## Following one operation

```python
import battread

details = battread.inspect("measurement.csv")
for candidate in details.columns:
    print(candidate.source_column, candidate.state, candidate.evidence)

data = battread.read("measurement.csv")
battread.write(data, "standardized.parquet")
```

`inspect` explains source columns; it does not certify every data row. `read`
collects standardized chunks into a DataFrame. When only a file is needed,
`convert` consumes the chunks directly and publishes output after successful
completion. Incremental iteration does not guarantee bounded input memory for
every adapter: MPR uses bounded binary batches, while Neware binary processing can
retain checkpoint metadata. Consult each reader's docstrings and capabilities.

Direct current takes precedence even if its values are missing. Reconstruction
is a fallback requiring established semantics; it must never fill arbitrary
holes in measured current. Missing rows remain in place. Time is checked across
missing values and chunk boundaries, and must never be silently sorted.

## Documentation required for every change

Every module, class and function needs an English docstring, including private
helpers, tests, fixtures and nested callbacks. Explain purpose and usage; for
non-obvious behavior, explain the reason. A one-line description is sufficient
only when it fully explains a simple operation or exception category.

Public functions use Google-style `Args`, `Returns` or `Yields`, `Raises`,
`Warns` and `Examples` sections where applicable. Describe source units, output
units, missing data, mutation, allocation and I/O when relevant. Examples that
need an external acquisition should be marked `doctest: +SKIP` and must not
pretend the file is included in the repository.

Stateful helpers need lifecycle explanations: construct once per source, call
methods in the documented order, preserve state between chunks, and finalize
after exhaustion. A reader method should explain which parsing plan it uses,
what it returns and which source assumptions justify its interpretation.

Comments belong beside decisions whose rationale is difficult to infer. Explain
why a unit must remain case-sensitive, why an interval cannot bridge a missing
row, or why publication uses an atomic filesystem operation. Avoid comments
that merely repeat assignments. Constants and declarative tables should have
nearby context or a module explanation covering their meaning and provenance.

Each test docstring names the invariant or regression it protects. Assertions
and fixture values specify the expected outcome; helper docstrings explain how
the test input is constructed. Add extra rationale for unusual synthetic data
or an independently established scientific reference.

Run `python tools/check_code_docs.py`. CI and pre-commit reject missing or empty
docstrings; overload stubs inherit implementation documentation. This check
cannot judge correctness, comprehensibility or language. Reviewers must verify
that explanations match the implementation, that examples are usable, and that
scientific assumptions and limitations are explicit.
