# Before publication

Author and maintainer: **Alessandro Gregucci**. Substantial AI assistance is
disclosed in `README.md` and described in `AUTHORS.md`.
All material intended for the GitHub repository must be in English.

Release metadata:

- Version: `0.1.0`, prepared on 2026-10-05; actual publication date is unset.
- Copyright: 2026 Alessandro Gregucci for original contributions; see COPYRIGHT.md.
- Security channel: GitHub private vulnerability reporting, described in SECURITY.md.
  Activation requires authenticated repository access and remains unverified.

Completed preparation checks:

- Windows and Ubuntu Python 3.11-3.14, with current and minimum dependencies:
  570 core-only tests pass with 38 expected vendor skips; all 608 tests pass
  with both vendor extras. Strict Pyright has zero errors in every environment.
- Ruff lint/format, documentation presence, strict MkDocs, wheel/source builds,
  dependency consistency and all pre-commit hooks pass.
- License texts, copyright, authorship, AI disclosure and artifact boundaries
  have been checked. Public fixture bytes are preserved.
- Publication uses an explicit file allowlist, known-private-copy/reference
  checks and a public-file SHA-256 manifest. Private inputs, derivatives,
  notebooks and caches are excluded. Review the final staging area again before
  any future upload; do not manually add excluded files.

Remote actions remaining at publication:

- After an authorized upload, verify the configured GitHub Actions jobs.
- Enable/verify GitHub private vulnerability reporting when available for the
  repository. No authenticated GitHub session was available during preparation;
  a public API lookup cannot establish settings for a private repository.
- Set the actual publication date when publishing. Version 0.1.0 is prepared;
  no push, public-visibility change or release publication has been performed.

The reviewed source snapshot is generated below
`.cache/publication/battread-0.1.0`; the source ZIP and wheel/source distributions
are in `dist/`. See the publication guide and compatibility report for the
procedure and exact local checks.

Publication policy:

- The project was developed privately; the maintainer reports no university
  or laboratory publication restrictions.
- Only synthetic examples and separately licensed, documented test fixtures
  may be published. User-provided experimental inputs and their derivatives
  or identifying summaries must not be included.
- The software carries no warranty or support commitment. Users must verify
  scientific outputs independently; GPL sections 15-17 govern liability limits
  subject to applicable law.

The official repository is https://github.com/GregAlex7zZ/battread.
Ordinary bug reports use https://github.com/GregAlex7zZ/battread/issues.
Documentation is included in the repository; a separate hosted documentation
website is optional and has not been configured. Local metadata updates do not
publish files or establish that GitHub settings or remote CI have been verified.
The current Neware workflow uses CSV autoexports. Further NDA/NDAX binary
validation is deferred to future releases and tracked in `TODO.md`.

Known limitations:

- Galvani loads the entire MPR file, including when using `iter_read()`.
- NDA/NDAX files with unknown framing or conflicting timestamps are rejected.
  Binary support is experimental, with limited real-acquisition coverage.
- Missing time in sparsely timestamped NDAX files remains NaN; it is not interpolated.
- Automatic Total Time selection in Neware CSV requires the verified header
  profile; other variants may require explicit mapping.
- Local benchmarks do not yet cover multi-GB files.

No silent scientific errors are known in the verified fixtures. Check details
and limitations in `docs/testing/V0_1_ACCEPTANCE_REPORT.md`.
