# Third-party dependency inventory

**Status:** local implementation and artifact audit, checked on 2026-10-05.

The packages below are declared in `pyproject.toml`. The prospective set was
installed together on CPython 3.14, imported successfully, and exercised with a
pandas/PyArrow Parquet round trip. Minimum versions preserve the Python 3.11
project floor; continuous integration is configured for the supported Python
versions but has not run in this source workspace.

| Dependency | Purpose | Group | Declared constraint | License metadata | Compatibility evidence |
|---|---|---|---|---|---|
| NumPy | Numeric operations | Core | `>=1.26.4` | BSD-3-Clause plus licenses for bundled components; [upstream license](https://github.com/numpy/numpy/blob/main/LICENSE.txt) | 2.5.3 imported on Python 3.14; the lower bound retains Python 3.11 support |
| pandas | Public DataFrame interface | Core | `>=2.2.3` | BSD-3-Clause; [upstream license](https://github.com/pandas-dev/pandas/blob/main/LICENSE) | 3.0.6 imported and round-tripped through PyArrow |
| PyArrow / Apache Arrow | Parquet and Arrow operations | Core | `>=15.0.2` | Apache-2.0 with bundled-component notices; [upstream license inventory](https://github.com/apache/arrow/blob/main/LICENSE.txt) | 25.0.1 imported and completed a Parquet round trip |
| Galvani | Bio-Logic MPR reader backend | `biologic`, `all` | `>=0.5.0,<0.6` | GPL-3.0-or-later in [publisher metadata](https://pypi.org/project/galvani/0.5.0/) | 0.5.0 tested against an independently parsed BT-Lab ASCII export on Python 3.14 |
| NewareNDA | Neware reader backend | `neware`, `all` | `==2026.6.11` | BSD-3-Clause in [publisher metadata](https://pypi.org/project/NewareNDA/2026.6.11/) | Real NDA29/NDC16 fixtures and synthetic fixtures for every supported layout on Python 3.14 |

The locally resolved transitive runtime set includes python-dateutil
2.9.0.post0 (its distributed dual BSD/Apache license), six 1.17.0 (MIT),
tzdata 2026.5 (Apache-2.0 metadata and its bundled timezone notices), and
xmltodict 1.0.4 (MIT, through NewareNDA). Versions and requirements are taken
from the installed distribution metadata; different Python/platform resolvers
can select a different set. NewareNDA's importlib-metadata requirement applies
only below Python 3.8 and is inactive for battread's supported versions.

## Incorporated material and artifact boundaries

### Backend credits

- **Galvani**, by Chris Kerr and contributors, provides the binary Bio-Logic
  MPR decoder used through its optional API. Its implementation is not copied
  into battread. Project: https://github.com/echemdata/galvani; the audited
  release is 0.5.0, GPL-3.0-or-later.
- **NewareNDA**, by Daniel Cogswell and contributors, provides the optional
  raw Neware decoders. Its record-layout definitions also informed adapted
  code in `src/battread/readers/neware.py`. Project:
  https://github.com/d-cogswell/NewareNDA; the audited release is 2026.6.11,
  BSD-3-Clause, copyright 2022-2024 SES AI Corporation.

These credits describe technical contributions and do not imply endorsement
of battread by the projects, their authors or their copyright holders.

The wheel contains battread source and its license material. It does not
bundle NumPy, pandas, Arrow, Galvani, NewareNDA or their binaries. Runtime
packages are separately resolved dependencies retaining their own distributed
licenses and bundled-component notices. Development tools and generated MkDocs
assets are not included in the wheel or source distribution.

Neware block layouts in the strict adapter are adapted from NewareNDA. Its
unchanged BSD-3-Clause copyright/license is retained in
`licenses/NewareNDA-BSD-3-Clause.txt`, referenced by the adapter and included in
both wheel license metadata and the source distribution. Galvani is used via
its optional adapter API; no Galvani implementation is vendored.

The source distribution includes the attributed Bio-Logic and Neware test
fixtures, adjacent licenses, documentation and reproducible benchmarks.
Private local acquisitions, profiling references, caches, virtual environments
and generated build/site directories are excluded. Artifact checks verify
those exclusions and retained licenses.

Galvani's GPL-3.0-or-later license is compatible with this project's
GPL-3.0-or-later license. The BSD and Apache dependencies are permissive, with
their notice and attribution requirements retained. Optional backend isolation
defines installation and import boundaries; it does not replace release-time
review of the exact artifacts distributed.

## Bio-Logic test acquisitions

The unchanged `020-formation_CB5.mpr` and `.mpt` fixtures are copyright
**Chihyu Chen <chihyu.chen@molicel.com>**, licensed **CC-BY-4.0** according to
their adjacent upstream `.license` files. They are test data, not GPL library
code, and retain their own license. Their provenance, hashes, independent
reference, attribution, and modifications made only to runtime test derivatives
are recorded in [the fixture README](tests/data/biologic/README.md).
See the [CC-BY-4.0 legal terms](https://creativecommons.org/licenses/by/4.0/legalcode.en).

## Release work still required

The Windows/Linux Python 3.11-3.14 and minimum-core matrix passed on
2026-10-05. Exact configurations and passing strict static checks
are recorded in [the compatibility report](docs/testing/PYTHON_COMPATIBILITY.md).
Local Ubuntu runtime, dependency and strict typing checks pass. Remote GitHub
Actions results remain pending.

Before a release, maintainers must:

- Run the configured Linux CI for the minimum dependency set on CPython 3.11
  and current dependencies on every supported interpreter.
- Recheck dependency versions, bundled-component notices and artifact contents
  for the final release environment. A distribution that bundles dependencies
  or publishes generated documentation requires a separate asset/license review.
- Retain COPYRIGHT.md, AUTHORS.md and the unmodified upstream notices.
  Copyright attribution and AI disclosure are finalized for the prepared release.

The complete project license text is in [LICENSE](LICENSE). This inventory must
be updated with release-specific evidence and notices during implementation.

## Neware fixtures

Copyright (c) 2022-2024 SES AI Corporation, BSD-3-Clause. The unchanged license
is included in `tests/data/neware/LICENSE`. `small.ndax` and `conflicting.ndax`
are unchanged; `prefix.nda` is an explicitly documented prefix derivative.
Source commit, modifications, wire-field references, backend version and
synthetic layout coverage are recorded in
[the fixture README](tests/data/neware/README.md).
