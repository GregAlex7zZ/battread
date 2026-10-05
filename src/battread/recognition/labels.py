# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Header normalization and unit extraction."""

import re
import unicodedata
from dataclasses import dataclass

from battread.normalization.units import Quantity as UnitQuantity
from battread.normalization.units import identify_unit, known_unit_aliases

_SPACE_RE = re.compile(r"\s+")
_PUNCTUATION_RE = re.compile(r"[_.,:;\\|]+")
_BRACKETED_UNIT_RE = re.compile(r"^(?P<label>.*?)\s*[\[(](?P<unit>[^\])]+)[\])]\s*$")
_DERIVED_UNIT_RE = re.compile(r"^(?:m?A(?:h)?|C)/(?:g|kg|L|cm(?:2|²)|m(?:2|²))$")


@dataclass(frozen=True, slots=True)
class ParsedLabel:
    """Retain normalized label text and physical-unit evidence separately.

    parse_label() constructs this record. raw_label preserves source text;
    normalized_label supports exact alias lookup. unit_expression retains the
    suffix, unit_quantity identifies its physical dimension, and canonical_unit
    is the registry's preferred source-unit spelling, preserving conversion scale.
    derived_unit marks supported detection of normalized units such as mAh/g,
    which cannot be treated as ordinary capacity without further physical data.
    """

    raw_label: str
    normalized_label: str
    unit_expression: str | None
    unit_quantity: UnitQuantity | None
    canonical_unit: str | None
    derived_unit: bool


def normalize_label(label: str | int) -> str:
    """Normalize text for exact alias lookup without fuzzy scientific inference.

    Accept a source string or positional integer. Return NFC text with casefolded
    quantity words, normalized separators and collapsed whitespace. Parse unit
    suffixes separately first: unit symbols must keep their SI prefix case.

    Examples:
        >>> normalize_label(" Cell_Current ")
        'cell current'
    """
    text = unicodedata.normalize("NFC", str(label)).casefold()
    text = text.replace("-", " ").replace("/", " ")
    text = _PUNCTUATION_RE.sub(" ", text)
    text = re.sub(r"[\[\](){}]", " ", text)
    return _SPACE_RE.sub(" ", text).strip()


def _unit_details(
    expression: str,
) -> tuple[str, UnitQuantity | None, str | None, bool]:
    """Parse a unit suffix without weakening SI case or ignoring derived units.

    Return the original normalized expression, quantity, scale-preserving
    registered spelling and derived-unit flag. Unknown units remain explicit
    so later recognition can explain why automatic selection is unsafe.
    """
    unit = unicodedata.normalize("NFC", expression.strip())
    identified = identify_unit(unit)
    if identified is not None:
        quantity, canonical = identified
        return unit, quantity, canonical, False
    compact = unit.replace(" ", "")
    return unit, None, None, _DERIVED_UNIT_RE.fullmatch(compact) is not None


def parse_label(label: str | int) -> ParsedLabel:
    """Separate a source header's quantity label from its unit evidence.

    Accept text or a positional identifier. Inspect bracketed, slash-separated
    and registered suffix units in a fixed order, then return ParsedLabel.
    Unknown bracketed units remain explicit; derived units are flagged rather
    than interpreted as an ordinary current or capacity. No values are examined.

    Examples:
        >>> label = parse_label("Current(mA)")
        >>> (label.normalized_label, label.unit_expression)
        ('current', 'mA')
    """
    raw = unicodedata.normalize("NFC", str(label)).strip()

    bracketed = _BRACKETED_UNIT_RE.fullmatch(raw)
    if bracketed is not None and bracketed.group("label").strip():
        unit, quantity, canonical, derived = _unit_details(bracketed.group("unit"))
        return ParsedLabel(
            raw,
            normalize_label(bracketed.group("label")),
            unit,
            quantity,
            canonical,
            derived,
        )

    if "/" in raw:
        prefix, expression = raw.split("/", maxsplit=1)
        if prefix.strip():
            unit, quantity, canonical, derived = _unit_details(expression)
            if quantity is not None or derived:
                return ParsedLabel(
                    raw,
                    normalize_label(prefix),
                    unit,
                    quantity,
                    canonical,
                    derived,
                )

    for alias in known_unit_aliases():
        suffix = f" {alias}"
        if raw.endswith(suffix) and raw[: -len(suffix)].strip():
            unit, quantity, canonical, derived = _unit_details(alias)
            return ParsedLabel(
                raw,
                normalize_label(raw[: -len(suffix)]),
                unit,
                quantity,
                canonical,
                derived,
            )

    return ParsedLabel(raw, normalize_label(raw), None, None, None, False)
