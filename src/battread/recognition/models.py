# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Immutable recognition result models."""

from dataclasses import dataclass
from typing import Literal, TypeAlias

Quantity: TypeAlias = Literal["time", "current", "voltage", "capacity", "unknown"]
KnownQuantity: TypeAlias = Literal["time", "current", "voltage", "capacity"]
CapacitySemantic: TypeAlias = Literal[
    "cumulative_signed",
    "delta_signed",
    "charge_capacity",
    "discharge_capacity",
    "generic_capacity",
    "unknown_capacity",
]
IntervalAlignment: TypeAlias = Literal["previous", "next"]
RecognitionState: TypeAlias = Literal["resolved", "ambiguous", "unresolved", "explicit"]


@dataclass(frozen=True, slots=True)
class ColumnMatch:
    """Explain the recognition decision for one source column.

    Inspect these immutable records before resolving an uncertain source. Scores
    describe declarative evidence, not probabilities; state and evidence govern
    whether automatic selection is allowed. A recognized quantity without a unit
    does not establish a safe numeric conversion.

    Attributes:
        source_column: Original label or positional identifier.
        source_position: Zero-based source position, preserving duplicate labels.
        quantity: Time, current, voltage, capacity or unknown.
        unit: Recognized source unit spelling, or None if not established.
        semantic: Capacity meaning, when supported by evidence.
        interval_alignment: Previous/next alignment for signed delta capacity.
        state: Resolved, ambiguous, unresolved or explicitly selected.
        confidence: Deterministic evidence score.
        evidence: Reasons for acceptance, rejection or uncertainty.
    """

    source_column: str | int
    source_position: int
    quantity: Quantity
    unit: str | None
    semantic: CapacitySemantic | None
    interval_alignment: IntervalAlignment | None
    state: RecognitionState
    confidence: float
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InspectionResult:
    """Describe source parsing and explain all column candidates.

    Returned by inspect() without producing a canonical measurement frame. The
    result is small, but inspection memory and scanning depend on the adapter;
    MPR inspection uses a backend load rather than a bounded input sample.

    Attributes:
        format: Source format identifier.
        reader: Selected registry adapter name.
        columns: Per-column decisions, including rejected and ambiguous candidates.
        delimiter: Established text separator, or None for a nontext source.
        decimal_separator: Established decimal convention, if applicable.
        encoding: Selected text encoding, if applicable.
        current_reconstruction_required: False for usable direct-current evidence,
            True for established capacity reconstruction, None when undetermined.
            Inspection does not certify the validity of every scientific row.
    """

    format: str
    reader: str
    columns: tuple[ColumnMatch, ...]
    delimiter: str | None = None
    decimal_separator: str | None = None
    encoding: str | None = None
    current_reconstruction_required: bool | None = None


@dataclass(frozen=True, slots=True)
class ReaderHint:
    """Carry authoritative vendor metadata into conservative recognition.

    Adapters may supply hints only for understood source layouts. A hint provides
    format knowledge; it must not be used to conceal conflicting scientific data.

    Attributes:
        source_column: Label or positional identifier receiving the hint.
        quantity: Known physical quantity.
        unit: Established source unit, if known.
        semantic: Established capacity meaning, if relevant.
        interval_alignment: Established signed delta interval convention.
        source_position: Optional exact position to distinguish duplicate labels.
    """

    source_column: str | int
    quantity: KnownQuantity
    unit: str | None = None
    semantic: CapacitySemantic | None = None
    interval_alignment: IntervalAlignment | None = None
    source_position: int | None = None
