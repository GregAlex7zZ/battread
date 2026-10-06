# Development

Install the development environment:

```bash
python -m pip install -e ".[dev,docs,all]"
```

Run these checks from the project root:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python tools/check_code_docs.py
python -m pyright --pythonpath "$(python -c 'import sys; print(sys.executable)')"
python -m mkdocs build --strict
python -m build
```

In PowerShell, the Pyright command above also resolves the active interpreter.
Install Git hooks with `pre-commit install`; run `pre-commit run --all-files`
before committing. CI checks Python 3.11-3.14, minimum core dependencies and
optional reader installations. Binary-reader tests need their respective extras.

See the [code guide](code-guide.md), [dependency policy](dependencies.md),
[benchmarks](benchmarks.md) and [MPR architecture](mpr-reader.md).
Contributor instructions are in the root `CONTRIBUTING.md`.
