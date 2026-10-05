# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Small, explicit unit conversion registry for canonical quantities."""

import unicodedata
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final, Literal, TypeAlias, cast

import numpy as np
from numpy.typing import NDArray

from battread.exceptions import (
    IncompatibleDataError,
    InvalidUnitError,
    UnknownUnitError,
)

Quantity: TypeAlias = Literal["time", "current", "voltage", "capacity"]

_CANONICAL_UNITS: Final[Mapping[Quantity, str]] = MappingProxyType(
    {
        "time": "s",
        "current": "mA",
        "voltage": "V",
        "capacity": "mAh",
    }
)


def _aliases(entries: Mapping[str, float]) -> Mapping[str, float]:
    """Build explicit accepted unit spellings for one conversion scale.

    Registry construction uses this helper to group documented aliases.
    Aliases do not permit arbitrary case folding: SI prefixes must retain
    their scientific meaning.
    """
    return MappingProxyType(dict(entries))


_FACTORS: Final[Mapping[Quantity, Mapping[str, float]]] = MappingProxyType(
    {
        "time": _aliases(
            {
                "s": 1.0,
                "sec": 1.0,
                "secs": 1.0,
                "second": 1.0,
                "seconds": 1.0,
                "ms": 1e-3,
                "msec": 1e-3,
                "msecs": 1e-3,
                "millisecond": 1e-3,
                "milliseconds": 1e-3,
                "us": 1e-6,
                "µs": 1e-6,
                "μs": 1e-6,
                "microsecond": 1e-6,
                "microseconds": 1e-6,
                "min": 60.0,
                "mins": 60.0,
                "minute": 60.0,
                "minutes": 60.0,
                "h": 3600.0,
                "hr": 3600.0,
                "hrs": 3600.0,
                "hour": 3600.0,
                "hours": 3600.0,
                "d": 86400.0,
                "day": 86400.0,
                "days": 86400.0,
            }
        ),
        "current": _aliases(
            {
                "A": 1000.0,
                "amp": 1000.0,
                "amps": 1000.0,
                "ampere": 1000.0,
                "amperes": 1000.0,
                "mA": 1.0,
                "mamp": 1.0,
                "mamps": 1.0,
                "milliamp": 1.0,
                "milliamps": 1.0,
                "milliampere": 1.0,
                "milliamperes": 1.0,
                "uA": 1e-3,
                "µA": 1e-3,
                "μA": 1e-3,
                "microamp": 1e-3,
                "microamps": 1e-3,
                "microampere": 1e-3,
                "microamperes": 1e-3,
                "nA": 1e-6,
                "nanoamp": 1e-6,
                "nanoamps": 1e-6,
                "nanoampere": 1e-6,
                "nanoamperes": 1e-6,
            }
        ),
        "voltage": _aliases(
            {
                "V": 1.0,
                "volt": 1.0,
                "volts": 1.0,
                "mV": 1e-3,
                "millivolt": 1e-3,
                "millivolts": 1e-3,
                "uV": 1e-6,
                "µV": 1e-6,
                "μV": 1e-6,
                "microvolt": 1e-6,
                "microvolts": 1e-6,
            }
        ),
        "capacity": _aliases(
            {
                "Ah": 1000.0,
                "A.h": 1000.0,
                "A h": 1000.0,
                "ampere hour": 1000.0,
                "ampere-hour": 1000.0,
                "mAh": 1.0,
                "mA.h": 1.0,
                "mA h": 1.0,
                "milliampere hour": 1.0,
                "milliampere-hour": 1.0,
                "uAh": 1e-3,
                "µAh": 1e-3,
                "μAh": 1e-3,
                "C": 1.0 / 3.6,
                "coulomb": 1.0 / 3.6,
                "coulombs": 1.0 / 3.6,
            }
        ),
    }
)

_UNIT_QUANTITIES: Final[Mapping[str, frozenset[Quantity]]] = MappingProxyType(
    {
        unit: frozenset(
            quantity for quantity, factors in _FACTORS.items() if unit in factors
        )
        for factors in _FACTORS.values()
        for unit in factors
    }
)

_PREFERRED_UNITS: Final[Mapping[Quantity, Mapping[float, str]]] = MappingProxyType(
    {
        "time": MappingProxyType(
            {1.0: "s", 1e-3: "ms", 1e-6: "us", 60.0: "min", 3600.0: "h", 86400.0: "d"}
        ),
        "current": MappingProxyType({1000.0: "A", 1.0: "mA", 1e-3: "uA", 1e-6: "nA"}),
        "voltage": MappingProxyType({1.0: "V", 1e-3: "mV", 1e-6: "uV"}),
        "capacity": MappingProxyType(
            {1000.0: "Ah", 1.0: "mAh", 1e-3: "uAh", 1.0 / 3.6: "C"}
        ),
    }
)


def _normalize_unit(unit: str) -> str:
    """Strip whitespace and normalize Unicode while preserving SI prefix case.

    Use before registry lookup; changing mA into MA would alter the physical
    scale, so unit normalization is deliberately narrower than label normalization.
    """
    return unicodedata.normalize("NFC", unit.strip())


def canonical_unit(quantity: Quantity) -> str:
    """Return the destination unit for a supported physical quantity.

    Time uses s, current mA, voltage V and capacity mAh. Adapters use this
    registry rather than maintaining inconsistent output-unit conventions.
    """
    return _CANONICAL_UNITS[quantity]


def identify_unit(unit: str) -> tuple[Quantity, str] | None:
    """Identify a registered unit spelling without weakening case rules.

    The returned spelling is normalized while preserving its conversion scale.
    This helper is used by header recognition before values are converted.
    """
    normalized = _normalize_unit(unit)
    quantities = _UNIT_QUANTITIES.get(normalized)
    if quantities is None or len(quantities) != 1:
        return None
    quantity = next(iter(quantities))
    factor = _FACTORS[quantity][normalized]
    return quantity, _PREFERRED_UNITS[quantity][factor]


def known_unit_aliases() -> tuple[str, ...]:
    """Return registered spellings, longest first, for header parsing."""
    return tuple(sorted(_UNIT_QUANTITIES, key=lambda value: (-len(value), value)))


def conversion_factor(quantity: Quantity, unit: str) -> float:
    """Return the multiplicative factor from *unit* to the canonical unit.

    Unit symbols remain case-sensitive. Only explicitly registered spellings
    are accepted.
    """
    normalized = _normalize_unit(unit)
    factors = _FACTORS[quantity]
    factor = factors.get(normalized)
    if factor is not None:
        return factor

    compatible_quantities = _UNIT_QUANTITIES.get(normalized)
    if compatible_quantities is not None:
        expected = canonical_unit(quantity)
        raise InvalidUnitError(
            f"Unit {unit!r} is incompatible with {quantity}; "
            f"expected a unit convertible to {expected!r}."
        )

    raise UnknownUnitError(
        f"Unknown {quantity} unit {unit!r}. "
        "Provide an explicitly supported unit spelling."
    )


def convert_to_canonical(
    values: object,
    *,
    quantity: Quantity,
    unit: str,
) -> NDArray[np.float64]:
    """Convert established physical units into a new float64 numeric array.

    Args:
        values: Numeric array-like input; NaNs retain their positions.
        quantity: Time, current, voltage or capacity.
        unit: Registered source unit with case-sensitive SI prefixes.

    Returns:
        A new array scaled to seconds, mA, V or mAh for the given quantity.
        Signs are preserved; this helper does not normalize time or validate order.

    Raises:
        UnknownUnitError: The spelling is unsupported.
        InvalidUnitError: A known unit belongs to a different physical quantity.
        IncompatibleDataError: Values cannot be represented numerically.

    Examples:
        >>> convert_to_canonical([0.001, -0.002], quantity="current", unit="A")
        array([ 1., -2.])
    """
    factor = conversion_factor(quantity, unit)
    try:
        array: NDArray[np.float64] = np.asarray(cast(Any, values), dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise IncompatibleDataError(
            f"{quantity.capitalize()} values are not numerically compatible."
        ) from error
    return cast(
        NDArray[np.float64],
        np.multiply(array, factor, dtype=np.float64),
    )
