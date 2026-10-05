# Contributing

Use English for all repository documentation, public examples, notebook text,
comments and user-facing messages. Preserve original source-data labels and
third-party notices where changing them would alter data or attribution.

Use Python 3.11 or later and install `python -m pip install -e ".[dev,docs,all]"`.
Run pytest, Ruff lint and format checks, Pyright with the active interpreter,
strict MkDocs build and package build before submitting a change.
Run `python tools/check_code_docs.py` as well. Every module, class and function
requires an English docstring, including private helpers, fixtures, tests and
benchmark code. Public APIs need argument and result descriptions, applicable
errors and warnings, and usage examples. Explain non-obvious scientific and
architectural decisions with nearby comments. Update explanations whenever
behavior changes. See [the code guide](docs/developer-guide/code-guide.md) and
[AGENTS.md](AGENTS.md); documentation quality is a required review criterion,
while the automatic check verifies presence only.
Run `pre-commit install` inside a Git checkout and
`pre-commit run --all-files` before committing. See
[publication preparation](docs/developer-guide/publication.md) for preparing a
reviewed source snapshot from a private workspace.

Follow the specifications under `docs/specification/`, the architecture and the
acceptance plan. Preserve direct current sign, time order, missing rows and
chunk equivalence. Scientific ambiguity must fail explicitly. Analysis features
are outside scope. Public APIs require strict type hints. Domain errors derive
from DataStandardizationError; warnings and logging use the standard Python frameworks.

Each non-trivial behavior needs tests. Real parsing or recognition failures need
regressions. Fixtures need redistribution permission, attribution, provenance,
hashes and an independent numerical reference. Label synthetic fixtures clearly.
Never publish user-provided acquisitions or derivatives without explicit
redistribution permission. This includes notebooks with saved outputs,
converted data, plots, filenames, source paths, hashes, row counts and summaries
that reveal private inputs. Use synthetic or independently licensed fixtures.
Keep private user acquisitions out of distributable test data and caches out of
artifacts. Alias additions should use the declarative registries and tests.
Architecture or interpretation changes need an ADR.

Run `python benchmarks/run.py` for timing/memory experiments; profile before
optimizing and establish numerical equivalence. Benchmarks have no arbitrary
speed threshold. See the developer guide for the local baselines.

Contributions are distributed under GPL-3.0-or-later, with separate licenses
retained for third-party fixtures. Communication should be respectful, concrete
and scientifically reviewable. The maintainer is Alessandro Gregucci.
The repository is https://github.com/GregAlex7zZ/battread. Report ordinary bugs
through its GitHub Issues. Private vulnerability reporting is the chosen
security channel; its GitHub activation remains to be verified. See SECURITY.md.

Disclose substantial AI assistance in contributions and describe the checks
performed. Generated code, tests and documentation require the same review as
other contributions; do not imply that automated checks are independent human
review. The project's existing AI contribution is documented in AUTHORS.md.
