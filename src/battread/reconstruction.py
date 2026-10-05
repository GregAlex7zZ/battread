# SPDX-FileCopyrightText: 2026 Alessandro Gregucci (battread contributions)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Conservative adjacent-row current reconstruction with bounded state."""

import math
from dataclasses import dataclass
from typing import Literal

from battread.exceptions import (
    CurrentReconstructionError,
    IncompatibleDataError,
    NonMonotonicTimeError,
)


@dataclass(slots=True)
class CurrentReconstructor:
    """Reconstruct interval current only after capacity semantics are established.

    Adapters convert time to seconds and capacity to mAh before using this helper.
    Construct once per source; observe() checks each original row, interval()
    evaluates adjacent rows, and finish() rejects an entirely unusable result.
    Never use it to replace or repair directly measured current.

    Attributes:
        kind: Signed cumulative capacity, signed delta capacity, or charge/discharge
            pair. A pair uses charge increase minus discharge increase.
        alignment: For delta_signed, "previous" uses the right row's capacity;
            "next" uses the left row's capacity for the interval between them.
        finite_count: Number of finite currents successfully reconstructed.
        monotonic_indices: Capacity positions that must not reset or decrease.
        last_finite_time: Last observed finite time for global order checks.
        last_capacities: Last finite capacities for monotonicity checks across NaNs.
    """

    kind: Literal["cumulative_signed", "delta_signed", "pair"]
    alignment: Literal["previous", "next"] = "previous"
    finite_count: int = 0
    monotonic_indices: tuple[int, ...] = ()
    last_finite_time: float | None = None
    last_capacities: tuple[float | None, ...] = (None, None)

    def observe(self, time: float, capacities: tuple[float, ...]) -> None:
        """Validate an original row and retain global monotonicity state.

        Pass elapsed seconds and one capacity value, or two for a charge/discharge
        pair, in original source order. Missing values remain missing. Raise on
        infinity, backwards time or a decrease in a capacity known to be monotonic.
        Observation does not calculate current or bridge a missing row.
        """
        if any(math.isinf(value) for value in (time, *capacities)):
            raise IncompatibleDataError("Reconstruction inputs contain infinity.")
        if math.isfinite(time):
            if self.last_finite_time is not None and time < self.last_finite_time:
                raise NonMonotonicTimeError("Source time moves backwards.")
            self.last_finite_time = time
        if self.kind == "pair" or self.monotonic_indices:
            remembered = list(self.last_capacities)
            for index, value in enumerate(capacities):
                if self.kind != "pair" and index not in self.monotonic_indices:
                    continue
                if not math.isfinite(value):
                    continue
                previous = remembered[index]
                if previous is not None and value < previous:
                    raise CurrentReconstructionError(
                        "Charge/discharge capacity decreases; "
                        "resets cannot be repaired."
                    )
                remembered[index] = value
            self.last_capacities = tuple(remembered)

    def interval(
        self,
        left: tuple[float, tuple[float, ...]],
        right: tuple[float, tuple[float, ...]],
    ) -> float:
        """Calculate current from two adjacent original rows without bridging gaps.

        Args:
            left: Earlier row as (time_s, capacity_values_mAh).
            right: Immediately following row in the same representation.

        Returns:
            Current in mA using 3600 * delta_capacity_mAh / delta_time_s.
            Missing inputs, duplicate time or an unusable interval produce NaN;
            no interpolation is attempted. A finite result increments finite_count.

        Raises:
            IncompatibleDataError: The calculated current overflows.
        """
        dt = right[0] - left[0]
        if not math.isfinite(dt) or dt <= 0:
            return math.nan
        if self.kind == "delta_signed":
            charge = (left if self.alignment == "next" else right)[1][0]
        else:
            charge = right[1][0] - left[1][0]
            if self.kind == "pair":
                charge -= right[1][1] - left[1][1]
        # Capacity is mAh while elapsed time is seconds: convert hours before
        # differentiating. Signed charge changes preserve current direction.
        current = 3600.0 * charge / dt
        if math.isinf(current):
            raise IncompatibleDataError("Reconstructed current overflows float64.")
        if math.isfinite(current):
            self.finite_count += 1
        return current

    def finish(self) -> None:
        """Reject a source whose reconstructed current contains no finite interval.

        Call after processing all rows. Raise CurrentReconstructionError instead of
        returning a dataset that appears successfully reconstructed but has no usable
        current. Boundary NaNs are allowed when other intervals are scientifically
        valid.
        """
        if self.finite_count == 0:
            raise CurrentReconstructionError(
                "Capacity reconstruction produced no finite current values."
            )
