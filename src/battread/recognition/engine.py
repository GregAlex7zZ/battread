# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Deterministic, conservative column-recognition engine."""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from battread.exceptions import AmbiguousColumnError, MissingColumnError
from battread.normalization.units import conversion_factor, identify_unit
from battread.recognition.labels import ParsedLabel, parse_label
from battread.recognition.models import (
    CapacitySemantic,
    ColumnMatch,
    InspectionResult,
    IntervalAlignment,
    KnownQuantity,
    ReaderHint,
)
from battread.recognition.registry import (
    CANONICAL_NAMES,
    CAPACITY_EXCLUSIONS,
    CURRENT_NEGATIVE_TERMS,
    EVIDENCE_CONFIDENCE,
    GENERIC_RULES,
    RESOLUTION_THRESHOLD,
    TIME_EXCLUSIONS,
    VENDOR_ALIASES,
    VOLTAGE_NEGATIVE_TERMS,
    AliasRule,
)


@dataclass(frozen=True, slots=True)
class _Candidate:
    """Keep explanatory match data separate from automatic-selection eligibility.

    An inspected column can carry useful evidence while remaining ineligible
    for a scientific choice; confidence alone is not a substitute for semantics.
    """

    match: ColumnMatch
    eligible: bool


def _contains_term(label: str, term: str) -> bool:
    """Match a complete normalized label term rather than an arbitrary substring.

    Negative evidence uses word boundaries so an unrelated label fragment
    does not accidentally reject a scientifically valid field.
    """
    return re.search(rf"(?:^| ){re.escape(term)}(?:$| )", label) is not None


def _label_quantity(label: str) -> KnownQuantity | None:
    """Identify a broad quantity family for applying negative-evidence rules.

    Return None when unknown. This does not resolve a source field; actual
    selection still requires registered aliases, units or authoritative hints.
    """
    if "time" in label.split() or label in {"timestamp", "datetime", "date"}:
        return "time"
    if "current" in label.split() or label in {"i", "icell", "i cell"}:
        return "current"
    if "voltage" in label.split() or "potential" in label.split():
        return "voltage"
    if (
        "capacity" in label.split()
        or label in {"cap", "q", "dq"}
        or "charge" in label.split()
    ):
        return "capacity"
    return None


def _negative_reason(parsed: ParsedLabel) -> tuple[KnownQuantity, str] | None:
    """Return a quantity and rejection reason for control or derived fields.

    Inspect ParsedLabel against exclusions and derived units. This keeps step
    time, limits, commanded values and normalized capacities from masquerading
    as measured absolute quantities. Return None when no exclusion applies.
    """
    label = parsed.normalized_label
    quantity = _label_quantity(label)

    if label in TIME_EXCLUSIONS:
        return "time", "excluded non-total time field"
    if label == "applied current":
        return "current", "applied current may be measured or commanded"
    if quantity == "current" and any(
        _contains_term(label, term) for term in CURRENT_NEGATIVE_TERMS
    ):
        return "current", "control, limit, or derived current field"
    if quantity == "voltage" and any(
        _contains_term(label, term) for term in VOLTAGE_NEGATIVE_TERMS
    ):
        return "voltage", "control, limit, or range voltage field"
    if quantity == "capacity" and any(
        _contains_term(label, term) for term in CAPACITY_EXCLUSIONS
    ):
        return "capacity", "normalized or derived capacity field"
    if parsed.derived_unit and quantity is not None:
        return quantity, "derived unit is incompatible with an absolute quantity"
    return None


def _unit_evidence(parsed: ParsedLabel, quantity: KnownQuantity) -> tuple[str, ...]:
    """Explain whether parsed units support the proposed quantity.

    Return evidence strings for unknown, incompatible or supported unit
    expressions. Evidence remains visible even when the candidate is rejected.
    """
    if parsed.unit_expression is None:
        return ()
    if parsed.unit_quantity is None:
        return (f"unit {parsed.unit_expression!r} is not registered",)
    if parsed.unit_quantity != quantity:
        return (f"unit {parsed.unit_expression!r} is incompatible with {quantity}",)
    return (f"compatible {quantity} unit {parsed.canonical_unit}",)


def _make_match(
    source: str | int,
    position: int,
    quantity: KnownQuantity,
    parsed: ParsedLabel,
    *,
    confidence: float,
    evidence: tuple[str, ...],
    semantic: CapacitySemantic | None = None,
    interval_alignment: IntervalAlignment | None = None,
    eligible: bool,
) -> _Candidate:
    """Create an unresolved positional candidate with evidence and eligibility.

    Attach known capacity semantics/alignment without resolving competition
    between columns. The separate _resolve pass handles scientific ambiguity.
    """
    alignment = interval_alignment
    return _Candidate(
        ColumnMatch(
            source_column=source,
            source_position=position,
            quantity=quantity,
            unit=parsed.canonical_unit,
            semantic=semantic,
            interval_alignment=alignment,
            state="unresolved",
            confidence=confidence,
            evidence=evidence,
        ),
        eligible,
    )


def _hint_candidate(
    source: str | int,
    position: int,
    parsed: ParsedLabel,
    hint: ReaderHint,
) -> _Candidate:
    """Apply reader-established quantity, unit and capacity semantics.

    Validate the hinted unit, then create an authoritative candidate. Hints
    are reserved for verified adapter semantics, not a guess based on sample values.
    """
    unit = hint.unit
    canonical = parsed.canonical_unit
    if unit is not None:
        conversion_factor(hint.quantity, unit)
        identified = identify_unit(unit)
        assert identified is not None
        canonical = identified[1]
    hinted = replace(parsed, canonical_unit=canonical)
    return _make_match(
        source,
        position,
        hint.quantity,
        hinted,
        confidence=EVIDENCE_CONFIDENCE["authoritative"],
        evidence=("authoritative reader-provided semantics",),
        semantic=hint.semantic,
        interval_alignment=hint.interval_alignment,
        eligible=True,
    )


def _matching_hint(
    source: str | int, position: int, hints: Sequence[ReaderHint]
) -> ReaderHint | None:
    """Find a positional hint before considering a label-only hint.

    Original positions distinguish duplicated source names. Reader adapters
    must supply consistent hints; return None when no hint describes the column.
    """
    positional = [hint for hint in hints if hint.source_position == position]
    if positional:
        return positional[0]
    named = [
        hint
        for hint in hints
        if hint.source_position is None and hint.source_column == source
    ]
    return named[0] if named else None


def _vendor_candidate(
    source: str | int,
    position: int,
    parsed: ParsedLabel,
    vendor: str | None,
) -> _Candidate | None:
    """Apply an exact vendor overlay only when label and unit both match.

    Return None outside the named vendor's registry. A vendor alias cannot
    justify a conflicting unit or a fuzzy scientific interpretation.
    """
    if vendor is None:
        return None
    for alias in VENDOR_ALIASES.get(vendor.casefold(), ()):
        if (
            parsed.normalized_label == alias.label
            and parsed.canonical_unit == alias.unit
        ):
            return _make_match(
                source,
                position,
                alias.quantity,
                parsed,
                confidence=EVIDENCE_CONFIDENCE["vendor"],
                evidence=(
                    f"exact {vendor} alias",
                    f"compatible {alias.quantity} unit {alias.unit}",
                ),
                semantic=alias.semantic,
                eligible=True,
            )
    return None


def _rule_candidate(
    source: str | int,
    position: int,
    parsed: ParsedLabel,
    rule: AliasRule,
) -> _Candidate:
    """Turn one declarative alias rule into an explained generic candidate.

    Combine its evidence class with unit compatibility and the resolution
    threshold. Incompatible or derived units make the field ineligible even
    when the label is otherwise a known alias.
    """
    unit_evidence = _unit_evidence(parsed, rule.quantity)
    incompatible = (
        parsed.unit_quantity is not None and parsed.unit_quantity != rule.quantity
    ) or parsed.derived_unit
    evidence_class = rule.evidence_class
    if evidence_class == "weak" and parsed.unit_quantity == rule.quantity:
        confidence_key = "weak_with_unit"
    else:
        confidence_key = evidence_class
    confidence = EVIDENCE_CONFIDENCE[confidence_key]
    eligible = confidence >= RESOLUTION_THRESHOLD and not incompatible
    evidence = (f"exact generic {evidence_class} alias", *unit_evidence)
    return _make_match(
        source,
        position,
        rule.quantity,
        parsed,
        confidence=confidence if not incompatible else 0.0,
        evidence=evidence,
        semantic=rule.semantic,
        eligible=eligible,
    )


def _candidate_for_column(
    source: str | int,
    position: int,
    *,
    vendor: str | None,
    hints: Sequence[ReaderHint],
) -> _Candidate:
    """Evaluate one field in precedence order while preserving source position.

    Reader hints and exact canonical names precede negative evidence, vendor
    aliases and generic rules. Unit-only evidence stays unresolved. No fuzzy
    matching or source-value heuristics may resolve scientific meaning here.
    """
    parsed = parse_label(source)
    hint = _matching_hint(source, position, hints)
    if hint is not None:
        return _hint_candidate(source, position, parsed, hint)

    canonical_quantity = CANONICAL_NAMES.get(str(source))
    if canonical_quantity is not None:
        canonical_units = {"time": "s", "current": "mA", "voltage": "V"}
        canonical = replace(
            parsed,
            canonical_unit=canonical_units[canonical_quantity],
            unit_quantity=canonical_quantity,
        )
        return _make_match(
            source,
            position,
            canonical_quantity,
            canonical,
            confidence=EVIDENCE_CONFIDENCE["canonical"],
            evidence=("exact canonical column name",),
            eligible=True,
        )

    negative = _negative_reason(parsed)
    if negative is not None:
        quantity, reason = negative
        return _make_match(
            source,
            position,
            quantity,
            parsed,
            confidence=EVIDENCE_CONFIDENCE["negative"],
            evidence=(reason,),
            eligible=False,
        )

    vendor_candidate = _vendor_candidate(source, position, parsed, vendor)
    if vendor_candidate is not None:
        return vendor_candidate

    for rule in GENERIC_RULES:
        if parsed.normalized_label in rule.aliases:
            return _rule_candidate(source, position, parsed, rule)

    numbered_current = re.fullmatch(r"current [0-9]+", parsed.normalized_label)
    if numbered_current is not None:
        rule = AliasRule("current", frozenset(), "moderate")
        candidate = _rule_candidate(source, position, parsed, rule)
        return replace(
            candidate,
            match=replace(
                candidate.match,
                evidence=(
                    "structured numbered-current pattern",
                    *_unit_evidence(parsed, "current"),
                ),
            ),
        )

    if parsed.unit_quantity is not None:
        quantity = parsed.unit_quantity
        return _make_match(
            source,
            position,
            quantity,
            parsed,
            confidence=EVIDENCE_CONFIDENCE["unit_only"],
            evidence=(f"compatible {quantity} unit without semantic label",),
            eligible=False,
        )

    return _Candidate(
        ColumnMatch(
            source_column=source,
            source_position=position,
            quantity="unknown",
            unit=None,
            semantic=None,
            interval_alignment=None,
            state="unresolved",
            confidence=EVIDENCE_CONFIDENCE["unrecognized"],
            evidence=("no registered semantic evidence",),
        ),
        False,
    )


def _resolution_key(candidate: _Candidate) -> tuple[str, str | None]:
    """Group competitors by quantity, separating distinct capacity roles.

    Charge and discharge capacities can coexist; two equally plausible cell
    voltages compete. This key lets _resolve apply that distinction explicitly.
    """
    match = candidate.match
    if match.quantity == "capacity":
        return match.quantity, match.semantic
    return match.quantity, None


def _resolve(candidates: list[_Candidate]) -> tuple[ColumnMatch, ...]:
    """Mark unique strongest candidates resolved and tied plausible fields ambiguous.

    Retain all columns and rejection evidence in source order. Never break
    a scientific tie by column position or by silently dropping a candidate.
    """
    eligible = [candidate for candidate in candidates if candidate.eligible]
    groups: dict[tuple[str, str | None], list[_Candidate]] = {}
    for candidate in eligible:
        groups.setdefault(_resolution_key(candidate), []).append(candidate)

    states: dict[int, str] = {}
    extra_evidence: dict[int, tuple[str, ...]] = {}
    for group in groups.values():
        best = max(candidate.match.confidence for candidate in group)
        winners = [
            candidate for candidate in group if candidate.match.confidence == best
        ]
        if len(winners) == 1:
            states[winners[0].match.source_position] = "resolved"
            for candidate in group:
                if candidate is not winners[0]:
                    extra_evidence[candidate.match.source_position] = (
                        "rejected because stronger semantic evidence exists",
                    )
        else:
            for winner in winners:
                states[winner.match.source_position] = "ambiguous"
                extra_evidence[winner.match.source_position] = (
                    "tied with another scientifically plausible candidate",
                )

    resolved: list[ColumnMatch] = []
    for candidate in candidates:
        match = candidate.match
        state = states.get(match.source_position, "unresolved")
        evidence = match.evidence + extra_evidence.get(match.source_position, ())
        resolved.append(replace(match, state=state, evidence=evidence))
    return tuple(resolved)


def recognize_columns(
    columns: Iterable[str | int],
    *,
    vendor: str | None = None,
    hints: Iterable[ReaderHint] = (),
) -> tuple[ColumnMatch, ...]:
    """Explain every source column using deterministic declarative evidence.

    Args:
        columns: Original source labels in order; duplicate labels retain positions.
        vendor: Optional vendor overlay identifier established by the reader.
        hints: Authoritative field metadata from an understood source layout.

    Returns:
        One ColumnMatch per input column, including unresolved and ambiguous
        candidates. Recognition does not convert values or silently break a genuine
        scientific tie. Pass the results to resolve_quantity() for strict selection.

    Examples:
        >>> matches = recognize_columns(["time/s", "Current(mA)", "Voltage(V)"])
        >>> [match.quantity for match in matches]
        ['time', 'current', 'voltage']
    """
    hint_sequence = tuple(hints)
    candidates = [
        _candidate_for_column(
            source,
            position,
            vendor=vendor,
            hints=hint_sequence,
        )
        for position, source in enumerate(columns)
    ]
    return _resolve(candidates)


def resolve_quantity(
    matches: Iterable[ColumnMatch],
    quantity: KnownQuantity,
    *,
    semantic: CapacitySemantic | None = None,
) -> ColumnMatch:
    """Select one established interpretation, explicitly rejecting uncertainty.

    Args:
        matches: Recognition results, optionally refined by explicit selectors.
        quantity: Required physical quantity.
        semantic: Optional capacity meaning to restrict the candidate set.

    Returns:
        The single resolved or explicitly selected ColumnMatch. The caller still
        verifies that its source unit permits the required conversion.

    Raises:
        AmbiguousColumnError: Relevant ambiguous or multiple selected matches remain.
        MissingColumnError: No relevant resolved or explicit match exists.
    """
    relevant = [
        match
        for match in matches
        if match.quantity == quantity
        and (semantic is None or match.semantic == semantic)
        and match.state in {"resolved", "ambiguous", "explicit"}
    ]
    ambiguous = [match for match in relevant if match.state == "ambiguous"]
    resolved = [match for match in relevant if match.state in {"resolved", "explicit"}]
    if ambiguous or len(resolved) > 1:
        candidates = ambiguous or resolved
        descriptions = ", ".join(
            f"{match.source_column!r} at position {match.source_position}"
            for match in candidates
        )
        raise AmbiguousColumnError(
            f"Ambiguous {quantity} columns: {descriptions}. "
            f"Specify the desired source explicitly with columns={{'{quantity}': ...}}."
        )
    if not resolved:
        raise MissingColumnError(f"No resolved {quantity} column was found.")
    return resolved[0]


def inspection_result(
    *,
    format: str,
    reader: str,
    columns: Iterable[str | int],
    vendor: str | None = None,
    hints: Iterable[ReaderHint] = (),
    delimiter: str | None = None,
    decimal_separator: str | None = None,
    encoding: str | None = None,
) -> InspectionResult:
    """Combine source metadata and column evidence without standardizing rows.

    Adapters provide original column labels, a registry reader name, format and
    any established vendor hints or text conventions. The immutable result
    retains all column decisions and a tri-state reconstruction indication:
    False for direct current, True for established capacity evidence, None for
    undetermined semantics. This indication is not whole-source validation.
    """
    matches = recognize_columns(columns, vendor=vendor, hints=hints)
    direct = any(
        match.quantity == "current"
        and match.state == "resolved"
        and match.unit is not None
        for match in matches
    )
    uncertain_current = any(
        match.quantity == "current" and match.state == "ambiguous" for match in matches
    )
    resolved_capacity = [
        match
        for match in matches
        if match.quantity == "capacity"
        and match.state == "resolved"
        and match.unit is not None
    ]
    semantics = {match.semantic for match in resolved_capacity}
    capacity = (
        "cumulative_signed" in semantics
        or (
            "delta_signed" in semantics
            and any(
                match.semantic == "delta_signed"
                and match.interval_alignment is not None
                for match in resolved_capacity
            )
        )
        or {"charge_capacity", "discharge_capacity"}.issubset(semantics)
    )
    reconstruction: bool | None
    if direct:
        reconstruction = False
    elif uncertain_current:
        reconstruction = None
    elif capacity:
        reconstruction = True
    else:
        reconstruction = None
    return InspectionResult(
        format=format,
        reader=reader,
        columns=matches,
        delimiter=delimiter,
        decimal_separator=decimal_separator,
        encoding=encoding,
        current_reconstruction_required=reconstruction,
    )
