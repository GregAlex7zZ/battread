# Developer guide

Create and activate a virtual environment, then install all development and
documentation dependencies:

```bash
python -m pip install -e ".[dev,docs,all]"
```

Run the foundation checks with:

```bash
ruff check .
ruff format --check .
pyright --pythonpath python
pytest
mkdocs build --strict
python -m build
```

Vendor fixtures must also run with each optional extra installed. CI checks
core-only installations and Python 3.11–3.14; the minimum core dependency job
uses Python 3.11. Local validation currently uses Python 3.14.6.
See [benchmarks](benchmarks.md) and [the acceptance report](../testing/V0_1_ACCEPTANCE_REPORT.md).
Contributor instructions are in the root `CONTRIBUTING.md`.
