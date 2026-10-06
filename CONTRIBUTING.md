# Contributing

Install the development environment with Python 3.11 or later:

```bash
python -m pip install -e ".[dev,docs,all]"
pre-commit install
```

Run the tests, lint, type, documentation and package checks listed in the
[developer guide](docs/developer-guide/index.md), and run
`pre-commit run --all-files` before committing.

Preserve measured-current sign and precedence, time order, missing rows and
chunk equivalence. Fail explicitly on scientific ambiguity. Add tests for
non-trivial changes and regressions for parsing or recognition bugs.

Write code and documentation in English. Document every function, including
private helpers and tests; use strict public API type hints. The
[code guide](docs/developer-guide/code-guide.md) explains the required detail.

Use synthetic or licensed examples, never private acquisitions or saved
notebook outputs. Retain third-party notices. Contributions are GPL-3.0-or-later.
Report problems through [GitHub Issues](https://github.com/GregAlex7zZ/battread/issues).
