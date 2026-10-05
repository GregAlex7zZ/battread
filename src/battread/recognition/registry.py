# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Declarative initial recognition registry."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

from battread.recognition.models import CapacitySemantic, KnownQuantity

EvidenceClass = Literal["strong", "moderate", "weak", "fallback"]


@dataclass(frozen=True, slots=True)
class AliasRule:
    """Declare exact normalized aliases with a shared scientific meaning.

    quantity supplies the physical dimension; aliases is a set of normalized
    labels; evidence_class sets declarative strength; semantic optionally
    establishes capacity meaning. Add supported aliases here with regression
    tests rather than introducing fuzzy or ad hoc branches in the engine.
    """

    quantity: KnownQuantity
    aliases: frozenset[str]
    evidence_class: EvidenceClass
    semantic: CapacitySemantic | None = None


@dataclass(frozen=True, slots=True)
class VendorAlias:
    """Declare a label/unit interpretation scoped to a verified vendor layout.

    label is the exact normalized text, unit supplies established source scale,
    quantity supplies dimension, and semantic optionally states capacity meaning.
    Vendor knowledge is applied only through a matching overlay, not to generic
    files that merely happen to contain a similar label.
    """

    label: str
    unit: str
    quantity: KnownQuantity
    semantic: CapacitySemantic | None = None


GENERIC_RULES: Final[tuple[AliasRule, ...]] = (
    AliasRule(
        "time",
        frozenset(
            {
                "time",
                "elapsed time",
                "elapsed",
                "test time",
                "total time",
                "experiment time",
                "measurement time",
                "run time",
                "runtime",
                "time elapsed",
                "total elapsed time",
            }
        ),
        "moderate",
    ),
    AliasRule("time", frozenset({"t"}), "weak"),
    AliasRule(
        "time",
        frozenset({"timestamp", "date time", "datetime", "absolute time", "date"}),
        "fallback",
    ),
    AliasRule(
        "current",
        frozenset(
            {
                "current",
                "cell current",
                "measured current",
                "measurement current",
                "current measured",
                "cellcurrent",
            }
        ),
        "moderate",
    ),
    AliasRule("current", frozenset({"i", "icell", "i cell"}), "weak"),
    AliasRule(
        "voltage",
        frozenset(
            {
                "voltage",
                "cell voltage",
                "measured voltage",
                "measurement voltage",
                "potential",
                "cell potential",
                "measured potential",
                "reference voltage",
                "working electrode voltage",
                "counter electrode voltage",
            }
        ),
        "moderate",
    ),
    AliasRule("voltage", frozenset({"v", "e", "u"}), "weak"),
    AliasRule(
        "capacity",
        frozenset(
            {
                "capacity",
                "cap",
                "q",
                "capacity passed",
                "charge passed",
                "total capacity",
            }
        ),
        "moderate",
        "generic_capacity",
    ),
    AliasRule(
        "capacity",
        frozenset(
            {
                "charge capacity",
                "charging capacity",
                "chg capacity",
                "chg cap",
                "charge cap",
                "q charge",
                "qcharge",
                "capacity charge",
                "charge q",
            }
        ),
        "strong",
        "charge_capacity",
    ),
    AliasRule(
        "capacity",
        frozenset(
            {
                "discharge capacity",
                "discharging capacity",
                "dchg capacity",
                "dchg cap",
                "discharge cap",
                "q discharge",
                "qdischarge",
                "capacity discharge",
                "discharge q",
            }
        ),
        "strong",
        "discharge_capacity",
    ),
    AliasRule(
        "capacity",
        frozenset(
            {
                "dq",
                "delta q",
                "delta capacity",
                "capacity increment",
                "incremental charge",
                "charge increment",
            }
        ),
        "moderate",
        "unknown_capacity",
    ),
)

TIME_EXCLUSIONS: Final[frozenset[str]] = frozenset(
    {
        "step time",
        "cycle time",
        "half cycle time",
        "segment time",
        "phase time",
        "pulse time",
        "rest time",
        "charge time",
        "charging time",
        "discharge time",
        "discharging time",
    }
)

CURRENT_NEGATIVE_TERMS: Final[frozenset[str]] = frozenset(
    {
        "range",
        "limit",
        "upper limit",
        "lower limit",
        "maximum",
        "minimum",
        "max",
        "min",
        "setpoint",
        "set point",
        "target",
        "programmed",
        "control",
        "compliance",
        "density",
        "specific",
        "threshold",
        "cutoff",
        "cut off",
        "command",
        "requested",
    }
)

VOLTAGE_NEGATIVE_TERMS: Final[frozenset[str]] = frozenset(
    {
        "limit",
        "upper limit",
        "lower limit",
        "maximum",
        "minimum",
        "max",
        "min",
        "setpoint",
        "set point",
        "target",
        "programmed",
        "control",
        "range",
        "cutoff",
        "cut off",
        "compliance",
        "threshold",
        "nominal",
        "command",
        "requested",
    }
)

CAPACITY_EXCLUSIONS: Final[frozenset[str]] = frozenset(
    {
        "specific capacity",
        "gravimetric capacity",
        "areal capacity",
        "volumetric capacity",
        "capacity density",
    }
)

VENDOR_ALIASES: Final[Mapping[str, tuple[VendorAlias, ...]]] = MappingProxyType(
    {
        "biologic": (
            VendorAlias("time", "s", "time"),
            VendorAlias("ewe", "V", "voltage"),
            VendorAlias("i", "mA", "current"),
            VendorAlias("dq", "mAh", "capacity", "unknown_capacity"),
        ),
        "neware": (),
    }
)

CANONICAL_NAMES: Final[Mapping[str, KnownQuantity]] = MappingProxyType(
    {"time_s": "time", "current_mA": "current", "voltage_V": "voltage"}
)

EVIDENCE_CONFIDENCE: Final[Mapping[str, float]] = MappingProxyType(
    {
        "authoritative": 1.0,
        "canonical": 0.95,
        "vendor": 0.90,
        "strong": 0.85,
        "moderate": 0.75,
        "weak_with_unit": 0.70,
        "fallback": 0.65,
        "weak": 0.40,
        "unit_only": 0.30,
        "negative": 0.0,
        "unrecognized": 0.0,
    }
)

RESOLUTION_THRESHOLD: Final = 0.60
