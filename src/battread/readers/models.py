# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Typed reader configuration and format metadata."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, TypeAlias

from battread.recognition.models import IntervalAlignment

SemanticKey: TypeAlias = Literal[
    "time",
    "current",
    "voltage",
    "capacity",
    "charge_capacity",
    "discharge_capacity",
]
SourceSelector: TypeAlias = str | int
ColumnMapping: TypeAlias = Mapping[SemanticKey, SourceSelector]
UnitMapping: TypeAlias = Mapping[SemanticKey, str]
HeaderOption: TypeAlias = Literal["infer"] | int | None
CapacityKind: TypeAlias = Literal["cumulative_signed", "delta_signed"]


def _empty_columns() -> ColumnMapping:
    """Create an immutable empty selector mapping for each ReadOptions default.

    A factory avoids shared mutable defaults while keeping adapter options read-only.
    """
    return MappingProxyType({})


def _empty_units() -> UnitMapping:
    """Create an immutable empty unit mapping for a default reader configuration."""
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class ReadOptions:
    """Immutable adapter configuration prepared by the public API.

    Construct via api._options() so selectors, units and text settings are
    validated consistently. Adapters consume this object rather than interpreting
    different keyword conventions. Direct construction does not validate fields.

    Attributes:
        columns: Semantic keys mapped to source labels or zero-based positions.
        units: Explicit physical unit declarations keyed by semantic quantity.
        capacity_kind: Declared signed cumulative or signed delta semantics.
        capacity_interval: Delta capacity's previous or next interval alignment.
        autodetect: Whether unspecified selectors may be recognized automatically.
        sep: Optional text delimiter.
        decimal: Optional decimal separator.
        encoding: Optional text encoding.
        header: "infer", physical header row index, or None for no header.
        skiprows: Number of leading physical lines to skip.
    """

    columns: ColumnMapping = field(default_factory=_empty_columns)
    units: UnitMapping = field(default_factory=_empty_units)
    capacity_kind: CapacityKind | None = None
    capacity_interval: IntervalAlignment | None = None
    autodetect: bool = True
    sep: str | None = None
    decimal: str | None = None
    encoding: str | None = None
    header: HeaderOption = "infer"
    skiprows: int = 0


@dataclass(frozen=True, slots=True)
class FormatInfo:
    """Explain which registered adapter was selected for an input.

    Returned by detect_format(); this identifies the container, not whether all
    scientific columns can be standardized. Use inspect() for column decisions.

    Attributes:
        format: Selected source format identifier.
        reader: Registry name of the chosen adapter.
        confidence: Deterministic evidence score, not a statistical probability.
        evidence: Human-readable reasons supporting the format selection.
    """

    format: str
    reader: str
    confidence: float
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReaderCapabilities:
    """Declare adapter operations for registry and caller decisions.

    Attributes:
        streaming: Whether input decoding supports incremental processing.
            Iterating an in-memory backend does not imply bounded-memory decoding.
        text_options: Whether delimiter, encoding and header overrides apply.
        formats: Source format identifiers supported by this adapter.
    """

    streaming: bool
    text_options: bool
    formats: tuple[str, ...]
