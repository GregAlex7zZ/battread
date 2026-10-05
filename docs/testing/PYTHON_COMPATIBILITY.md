# Python compatibility verification

Verified on 2026-10-05 using isolated **Windows x86-64** and **Ubuntu 24.04.5
x86-64** CPython environments.
The tests exercised the installed `battread` 0.1.0 wheel, not an editable source
checkout. Only the public licensed fixtures and synthetic test inputs were used.

## Runtime results

| Python | NumPy | pandas | PyArrow | Core-only suite | Suite with both vendor extras | Dependency consistency |
|---|---|---|---|---|---|---|
| 3.11.17 | 2.4.6 | 3.0.6 | 25.0.1 | 570 passed, 38 skipped | 608 passed | Passed |
| 3.12.15 | 2.5.3 | 3.0.6 | 25.0.1 | 570 passed, 38 skipped | 608 passed | Passed |
| 3.13.16 | 2.5.3 | 3.0.6 | 25.0.1 | 570 passed, 38 skipped | 608 passed | Passed |
| 3.14.8 | 2.5.3 | 3.0.6 | 25.0.1 | 570 passed, 38 skipped | 608 passed | Passed |
| 3.11.17, minimum core | 1.26.4 | 2.2.3 | 15.0.2 | 570 passed, 38 skipped | 608 passed | Passed |

The 38 core-only skips are the tests requiring unavailable vendor dependencies;
they all ran after installing the extras. Both vendor extras used Galvani 0.5.0
and NewareNDA 2026.6.11. pytest was 9.1.1. NumPy 2.4.6 was selected by the
resolver for Python 3.11; newer supported interpreters selected NumPy 2.5.3.
The minimum-core constraints also remained pinned when installing vendor extras.

Every final runtime suite passed; no scientific interpretation or conversion was
changed. The full suite includes publication privacy regressions and a regression
for importing the pandas typing boundary on every supported Python version.

## Static checks and documentation

Strict Pyright 1.1.414 passes with **zero errors and warnings** in all five
current/minimum environments, including source, tests and publication tools.
Ruff 0.16.10 lint and formatting, documentation presence checks and strict MkDocs
builds pass. Wheel and source builds pass.

Older pandas/NumPy typing overloads required a narrow private protocol boundary
around the existing pandas numeric coercion and NumPy export calls. This keeps
runtime behavior and the public API unchanged without disabling strict checks;
see ADR 0005. Regression tests verify coercion, missing positions and sign.

## Reproducing the checks

Create a fresh virtual environment using each selected interpreter, activate it,
build a wheel once, and run from the repository root:

```bash
python -m pip install "dist/battread-0.1.0-py3-none-any.whl[dev]"
python -m pip check
python -m pytest -q
python -m pip install "dist/battread-0.1.0-py3-none-any.whl[all]"
python -m pip check
python -m pytest -q
python -m pyright --pythonpath "$(python -c 'import sys; print(sys.executable)')"
```

For the minimum environment, include `numpy==1.26.4`, `pandas==2.2.3` and
`pyarrow==15.0.2` in both installation commands. On Windows, use a separate
pytest `--basetemp` and `-o cache_dir=...` for each environment if shared
temporary-directory permissions conflict. The first local attempt encountered
such permission errors; those runs were discarded and repeated with isolated
temporary directories. No scientific test was disabled to resolve them.

The local runs used uv-managed CPython installations without changing the
system interpreter or Windows interpreter registration. Detailed local logs
are kept outside publishable artifacts; the tables above contain only public
test and environment results.

## Linux results

Linux checks ran in a temporary, headless Ubuntu VM under QEMU. Only the same
public source, installed wheel, synthetic tests and licensed fixtures entered
the VM. No private experimental input or derivative was transferred. Emulated
execution times are not throughput benchmarks.

| Python | NumPy | pandas | PyArrow | Core-only suite | Both vendor extras | Strict Pyright errors |
|---|---|---|---|---|---|---|
| 3.11.17 | 2.4.6 | 3.0.6 | 25.0.1 | 570 passed, 38 skipped | 608 passed | 0 |
| 3.12.15 | 2.5.3 | 3.0.6 | 25.0.1 | 570 passed, 38 skipped | 608 passed | 0 |
| 3.13.16 | 2.5.3 | 3.0.6 | 25.0.1 | 570 passed, 38 skipped | 608 passed | 0 |
| 3.14.8 | 2.5.3 | 3.0.6 | 25.0.1 | 570 passed, 38 skipped | 608 passed | 0 |
| 3.11.17 (minimum) | 1.26.4 | 2.2.3 | 15.0.2 | 570 passed, 38 skipped | 608 passed | 0 |

Dependency consistency checks pass for all Linux environments. Ruff lint and
formatting, code documentation checks and strict MkDocs builds also pass on
Linux. Galvani 0.5.0 and NewareNDA 2026.6.11 were used on both operating systems.
The final publication regression checks were repeated after the filename guard
was strengthened; all five tests pass on both platforms.

## Limits of this evidence

This establishes the tested Windows/Linux configurations, not future dependency
versions or all vendor file variants. Linux GitHub Actions jobs are configured
but have not run remotely: local VM results are not GitHub Actions results.
macOS is unverified. Binary Neware coverage remains experimental.
