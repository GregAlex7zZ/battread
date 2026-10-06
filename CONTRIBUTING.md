# Contributing

Use Python 3.11 or later and install development dependencies:

```bash
python -m pip install -e ".[dev,docs,all]"
pre-commit install
```

Run pytest, Ruff lint/format checks, strict Pyright, the documentation-presence
check, strict MkDocs build and package build. Commands are in the
[developer guide](docs/developer-guide/index.md). CI checks supported Python
versions, optional readers and minimum core dependencies.

Preserve measured-current sign and precedence, time order, missing rows and
chunk equivalence. Scientific ambiguity must fail explicitly. All domain
exceptions derive from `DataStandardizationError`; warnings and logging use
Python's standard frameworks. Analysis features remain outside scope.

Document every Python module, class and function in English, including private
helpers, tests, fixtures and benchmarks. Explain purpose, usage and non-obvious
scientific choices. Public APIs require strict type hints and argument/result,
error, warning and memory documentation. See the
[code guide](docs/developer-guide/code-guide.md). Future additions follow the
same documentation standard.

Add tests for non-trivial behavior and a regression for each parsing or
recognition issue. Architecture or scientific interpretation changes need a
short decision record. Review results and document limitations accurately.

Never include private acquisitions, derivatives, identifying paths, hashes or
saved notebook outputs. Use synthetic examples or fixtures with documented
redistribution permission and independent references. Keep caches and build
artifacts out of Git. Preserve original fixture labels and third-party notices.

Contributions are GPL-3.0-or-later. Report ordinary bugs through
[GitHub Issues](https://github.com/GregAlex7zZ/battread/issues); see
[SECURITY.md](SECURITY.md) for security reports. The maintainer is Alessandro Gregucci.
