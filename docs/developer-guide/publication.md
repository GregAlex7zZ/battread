# Preparing a publication

Preparation does not upload files or change repository visibility. Keep private
experimental acquisitions, derivatives and notebooks outside the public tree.
Use only synthetic examples or independently licensed, attributed fixtures.

## Reviewed source snapshot

Run `python tools/prepare_publication.py` from a checked source checkout. Supply
`--private-input PATH` for each confidential input and derivative when checking
known copies and identifiers. These arguments remain local: do not commit a
list of private filenames or fingerprints. The tool selects an explicit
allowlist, rejects known private copies and identifiers, and creates a fresh
`.cache/publication/battread-0.1.0` folder with public-file SHA-256 hashes.
It refuses to overwrite an existing snapshot. For subsequent checks, supply
a new destination below `.cache/publication`.

The repository's `.gitattributes` preserves file bytes during Git checkout and
staging. This keeps licensed reference hashes and the publication manifest
valid across Windows and Linux. Source formatting is enforced by Ruff and
the documented editor conventions rather than Git line-ending conversion.

Review the snapshot for indirect disclosures too. Exact-copy checks cannot
identify every transformation of private data. Excluded notebooks and cached
outputs must not be reintroduced manually. Only the documented, separately
licensed test fixtures are included as scientific data.

## Final checks

In the reviewed snapshot, initialize a Git checkout and run:

```bash
python -m pip install -e ".[dev,docs,all]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m pyright --pythonpath python
python tools/check_code_docs.py
python -m mkdocs build --strict
python -m build
git add .
pre-commit run --all-files
git diff --cached --stat
```

Inspect staged paths, distribution contents, retained license texts, package
version, authorship and AI disclosure. Repeat the supported-Python and minimum
dependency matrix as described in the compatibility report. Update the
acceptance report and changelog with performed checks, without claiming a
release date before release.

## GitHub steps

The configured origin is `https://github.com/GregAlex7zZ/battread`. An empty or
private repository cannot demonstrate successful CI until code is uploaded.
After authorization to upload, check all configured GitHub Actions jobs and
enable the private vulnerability reporting channel documented in SECURITY.md
when GitHub makes it available. Review repository visibility before making
the repository public. Source preparation, uploading a private checkout,
making it public and publishing a release are distinct actions.
