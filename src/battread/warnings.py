# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Warning categories for recoverable data-quality conditions."""

from collections.abc import Mapping
from types import MappingProxyType


class DataStandardizationWarning(UserWarning):
    """Base class for all battread warnings."""


class MissingValueWarning(DataStandardizationWarning):
    """Report retained missing values in canonical columns."""

    affected_counts: Mapping[str, int]

    def __init__(self, affected_counts: Mapping[str, int]) -> None:
        """Copy per-column missing-row counts into an immutable warning payload.

        Use warnings.warn(MissingValueWarning(counts)) to expose both readable
        text and affected_counts. A caller's later mapping edits cannot change
        the warning; chunk counts can be summed across a streamed source.
        """
        counts = {column: int(count) for column, count in affected_counts.items()}
        self.affected_counts = MappingProxyType(counts)
        details = "\n".join(
            f"{column}: {count} {'row' if count == 1 else 'rows'}"
            for column, count in counts.items()
        )
        super().__init__(f"Standardized dataset contains missing values:\n{details}")


class PartialRecoveryWarning(DataStandardizationWarning):
    """Report a recoverable source irregularity."""


class MalformedValueWarning(PartialRecoveryWarning):
    """Report nonempty numeric cells retained as missing values."""

    affected_counts: Mapping[str, int]

    def __init__(self, affected_counts: Mapping[str, int]) -> None:
        """Record nonempty cells that failed numeric parsing without discarding rows.

        Copy the supplied per-column counts and format an actionable message.
        The malformed-value warning complements canonical missing-value reporting:
        its counts describe parsing failures rather than all missing source cells.
        """
        counts = {column: int(count) for column, count in affected_counts.items()}
        self.affected_counts = MappingProxyType(counts)
        details = ", ".join(f"{column}: {count}" for column, count in counts.items())
        super().__init__(f"Malformed numeric cells were retained as NaN ({details}).")
