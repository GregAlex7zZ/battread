# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Create a reviewable publication tree using an explicit file allowlist.

Run from the repository with --private-input FILE for each confidential input
or derivative to check. Input names and hashes are never saved in the output.
The snapshot contains source-relative public paths and a SHA-256 manifest.
This guard detects known copies and identifiers; it does not replace review
of documents for indirect disclosures or a review of the final Git staging area.
"""

import argparse
import hashlib
import shutil
import tomllib
from collections.abc import Iterable
from pathlib import Path

ROOT_FILES = (
    "README.md",
    "LICENSE",
    "COPYRIGHT.md",
    "AUTHORS.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "RELEASE_STATUS.md",
    "THIRD_PARTY_NOTICES.md",
    "TODO.md",
    "pyproject.toml",
    "mkdocs.yml",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".pre-commit-config.yaml",
)
SOURCE_PATTERNS = (
    "src/**/*.py",
    "src/**/py.typed",
    "tests/**/*.py",
    "docs/**/*.md",
    "tools/**/*.py",
    "licenses/*.txt",
    ".github/workflows/*.yml",
    "benchmarks/run.py",
    "benchmarks/README.md",
    "benchmarks/baseline-before.json",
    "benchmarks/baseline-after.json",
    "benchmarks/arrow-probe.json",
    "benchmarks/mpr_streaming.py",
    "benchmarks/mpr-memory.json",
)
# These are independently licensed fixtures, not maintainer-provided inputs.
PUBLIC_FIXTURES = (
    "tests/data/biologic/README.md",
    "tests/data/biologic/CC-BY-4.0.txt",
    "tests/data/biologic/020-formation_CB5.mpr",
    "tests/data/biologic/020-formation_CB5.mpr.license",
    "tests/data/biologic/020-formation_CB5.mpt",
    "tests/data/biologic/020-formation_CB5.mpt.license",
    "tests/data/neware/README.md",
    "tests/data/neware/LICENSE",
    "tests/data/neware/prefix.nda",
    "tests/data/neware/small.ndax",
    "tests/data/neware/conflicting.ndax",
)


def digest(path: Path) -> str:
    """Hash a file incrementally so large private inputs need not enter memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def publication_files(root: Path) -> list[Path]:
    """Select approved source/documentation paths and independently licensed data.

    Return sorted paths under root. Caches, notebook outputs, arbitrary data
    files and generated artifacts are omitted by construction. Reject aliases
    escaping root so a symlink cannot silently import an external private file.
    """
    root = root.resolve()
    selected = {
        root / name
        for name in (*ROOT_FILES, *PUBLIC_FIXTURES)
        if (root / name).is_file()
    }
    for pattern in SOURCE_PATTERNS:
        selected.update(path for path in root.glob(pattern) if path.is_file())
    if any(not path.resolve().is_relative_to(root) for path in selected):
        raise ValueError("A publication source path resolves outside the repository.")
    return sorted(selected, key=lambda path: path.relative_to(root).as_posix())


def check_private_material(
    files: Iterable[Path], private_inputs: Iterable[Path]
) -> None:
    """Reject exact known private copies, identifiers and published fingerprints.

    Private input paths are explicit local arguments, not a registry committed
    into the repository. All fingerprints and names remain in memory. Derived
    outputs must also be supplied if they need exact-copy detection; no claim
    is made about recognizing arbitrary transformations of scientific data.
    """
    fingerprints: set[str] = set()
    identifiers: set[str] = set()
    for path in private_inputs:
        fingerprints.add(digest(path))
        # Very short stems collide with ordinary units and scientific labels.
        # Exact contents are still checked regardless of filename length.
        identifiers.update(
            value.casefold() for value in (path.name, path.stem) if len(value) >= 8
        )
    for path in files:
        if any(value in path.name.casefold() for value in identifiers):
            raise ValueError(
                "Known private identifier found in a publication candidate."
            )
        if digest(path) in fingerprints:
            raise ValueError("Known private contents found in a publication candidate.")
        text = path.read_bytes().decode("utf-8", errors="ignore").casefold()
        if any(value in text for value in identifiers | fingerprints):
            raise ValueError(
                "Known private identifier found in a publication candidate."
            )


def prepare(root: Path, destination: Path, private_inputs: Iterable[Path]) -> int:
    """Copy reviewed candidates into a new private-cache snapshot with a manifest.

    Destination must be below root/.cache/publication and must not already
    exist. No original file is modified or deleted. Validate candidates before
    copying; the manifest records only public relative paths and public hashes.
    Return the number of copied source files. Uploading is a separate action.
    """
    root = root.resolve()
    destination = destination.resolve()
    allowed = (root / ".cache/publication").resolve()
    if destination == allowed or not destination.is_relative_to(allowed):
        raise ValueError(
            "Publication destination must be a child of .cache/publication."
        )
    if destination.exists():
        raise FileExistsError(
            "Publication destination already exists; no files changed."
        )
    files = publication_files(root)
    check_private_material(files, private_inputs)
    destination.mkdir(parents=True)
    manifest: list[str] = []
    for source in files:
        relative = source.relative_to(root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        manifest.append(f"{digest(target)}  {relative.as_posix()}")
    (destination / "PUBLICATION_MANIFEST.sha256").write_text(
        "\n".join(manifest) + "\n", encoding="utf-8"
    )
    return len(files)


def main() -> None:
    """Parse local input checks and create a version-labelled publication snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-input", type=Path, action="append", default=[])
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    destination = (
        args.destination
        or root / f".cache/publication/battread-{project['project']['version']}"
    )
    count = prepare(root, destination, args.private_input)
    print(f"Prepared {count} publication files; no upload performed.")


if __name__ == "__main__":
    main()
