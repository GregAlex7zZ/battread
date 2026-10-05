# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Synthetic publication-privacy regressions without any real private inputs."""

import importlib.util
from pathlib import Path
from typing import Protocol, cast

import pytest


class _PublicationTools(Protocol):
    """Type the tooling module without relying on it being an installed package."""

    def publication_files(self, root: Path) -> list[Path]:
        """Return allowlisted candidate files under the supplied source root."""
        ...

    def check_private_material(
        self, files: list[Path], private_inputs: list[Path]
    ) -> None:
        """Reject known confidential copies or identifying source references."""
        ...

    def prepare(self, root: Path, destination: Path, private_inputs: list[Path]) -> int:
        """Create a new cache snapshot after privacy validation."""
        ...


@pytest.fixture
def publication_tools() -> _PublicationTools:
    """Load the repository utility directly, including under installed-wheel tests.

    Tooling is not part of the library's public package. Loading by its known
    source path makes the test independent of pytest's executable import path.
    """
    path = Path(__file__).resolve().parents[1] / "tools/prepare_publication.py"
    spec = importlib.util.spec_from_file_location("publication_tools", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(_PublicationTools, module)


def test_allowlist_excludes_arbitrary_data_and_cached_outputs(
    tmp_path: Path, publication_tools: _PublicationTools
) -> None:
    """Unlisted raw CSVs and cached derivatives must never become candidates."""
    (tmp_path / "README.md").write_text("Synthetic documentation.", encoding="utf-8")
    (tmp_path / "measurement.csv").write_text("0,1,3", encoding="utf-8")
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache/derived.md").write_text(
        "Synthetic cached output.", encoding="utf-8"
    )
    assert publication_tools.publication_files(tmp_path) == [tmp_path / "README.md"]


def test_private_copy_is_rejected_even_when_renamed_as_documentation(
    tmp_path: Path, publication_tools: _PublicationTools
) -> None:
    """An allowed extension cannot disguise an exact confidential input copy."""
    private = tmp_path / "confidential-input.csv"
    candidate = tmp_path / "README.md"
    private.write_bytes(b"SYNTHETIC CONFIDENTIAL CONTENT\n")
    candidate.write_bytes(private.read_bytes())
    with pytest.raises(ValueError, match="private contents"):
        publication_tools.check_private_material([candidate], [private])


def test_private_filename_reference_is_rejected_without_publishing_the_name(
    tmp_path: Path, publication_tools: _PublicationTools
) -> None:
    """A report mentioning a confidential input is blocked before copying."""
    private = tmp_path / "synthetic-confidential-input.csv"
    private.write_bytes(b"FAKE INPUT\n")
    candidate = tmp_path / "README.md"
    candidate.write_text("A result from " + private.name, encoding="utf-8")
    with pytest.raises(ValueError, match="private identifier") as caught:
        publication_tools.check_private_material([candidate], [private])
    assert private.name not in str(caught.value)
    # Renaming a public file after a confidential source is also a disclosure.
    named_candidate = tmp_path / f"{private.stem}-report.md"
    named_candidate.write_text("Synthetic public contents.", encoding="utf-8")
    with pytest.raises(ValueError, match="private identifier"):
        publication_tools.check_private_material([named_candidate], [private])


def test_snapshot_contains_public_hashes_and_does_not_overwrite(
    tmp_path: Path, publication_tools: _PublicationTools
) -> None:
    """The reviewable snapshot preserves bytes and cannot replace an earlier copy."""
    source = tmp_path / "README.md"
    source.write_bytes(b"Synthetic public documentation.\n")
    target = tmp_path / ".cache/publication/review"
    assert publication_tools.prepare(tmp_path, target, []) == 1
    assert (target / "README.md").read_bytes() == source.read_bytes()
    assert "README.md" in (target / "PUBLICATION_MANIFEST.sha256").read_text()
    with pytest.raises(FileExistsError):
        publication_tools.prepare(tmp_path, target, [])


def test_snapshot_destination_cannot_escape_the_private_cache(
    tmp_path: Path, publication_tools: _PublicationTools
) -> None:
    """Reject destinations outside the designated cache before creating anything."""
    target = tmp_path / "unexpected"
    with pytest.raises(ValueError, match="destination"):
        publication_tools.prepare(tmp_path, target, [])
    assert not target.exists()
