# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Reader protocol used by the central registry."""

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pandas as pd

from battread.readers.models import FormatInfo, ReaderCapabilities, ReadOptions
from battread.recognition.models import InspectionResult


class Reader(Protocol):
    """Specify the structural adapter interface consumed by ReaderRegistry.

    Implement name, capabilities, detect(), inspect(), read() and iter_read().
    Registration does not require inheritance. Detection describes containers;
    inspection explains candidates; reading enforces the scientific contract.
    Declare streaming limitations honestly and import optional backends lazily.
    """

    name: str
    capabilities: ReaderCapabilities

    def detect(self, path: Path) -> FormatInfo | None:
        """Describe recognized source content, or return None to decline it.

        Implementations must not standardize rows here. The registry uses the
        returned confidence and evidence to select an adapter.
        """
        ...

    def inspect(self, path: Path, options: ReadOptions) -> InspectionResult:
        """Explain source columns and interpretation using validated reader options.

        Return an InspectionResult including unresolved or ambiguous candidates.
        Inspection need not guarantee whole-source validity; backend memory costs
        are declared in the reader guide.
        """
        ...

    def read(self, path: Path, options: ReadOptions) -> pd.DataFrame:
        """Return one complete canonical pandas DataFrame for the source.

        Use the shared options contract, preserve missing rows, and validate the
        whole source before returning. Optional backends must remain adapter-local.
        """
        ...

    def iter_read(
        self, path: Path, options: ReadOptions, *, chunk_size: int
    ) -> Iterator[pd.DataFrame]:
        """Yield canonical fragments while preserving one source's time and state.

        chunk_size is a positive row count supplied by the public boundary.
        Finish iteration to complete end-of-source checks; source streaming depends
        on declared adapter capabilities rather than this interface alone.
        """
        ...
