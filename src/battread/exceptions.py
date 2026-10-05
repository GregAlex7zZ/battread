# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Domain-specific exception hierarchy."""


class DataStandardizationError(Exception):
    """Base class for all battread domain errors."""


class UnsupportedFormatError(DataStandardizationError):
    """Raised when no registered reader supports a source format."""


class MissingColumnError(DataStandardizationError):
    """Raised when a required scientific quantity cannot be located."""


class AmbiguousColumnError(DataStandardizationError):
    """Raised when multiple unresolved scientific interpretations remain."""


class UnknownUnitError(DataStandardizationError):
    """Raised when a unit is outside the explicit unit registry."""


class InvalidUnitError(DataStandardizationError):
    """Raised when a known unit is incompatible with a quantity."""


class CurrentReconstructionError(DataStandardizationError):
    """Raised when current cannot be reconstructed safely."""


class IncompatibleDataError(DataStandardizationError):
    """Raised when data cannot satisfy the canonical scientific contract."""


class NonMonotonicTimeError(IncompatibleDataError):
    """Raised when finite elapsed time moves backwards."""


class CorruptedFileError(DataStandardizationError):
    """Raised when source corruption prevents safe interpretation."""


class MissingDependencyError(DataStandardizationError):
    """Raised when requested optional support is not installed."""


class OutputExistsError(DataStandardizationError):
    """Raised when output exists and replacement was not authorized."""
