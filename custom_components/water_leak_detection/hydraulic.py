"""Hydraulic plausibility helpers.

These calculations deliberately provide a heuristic reference envelope, not an
exact prediction of possible building flow. Real flow also depends on dynamic
pressure, meter/reducer characteristics, pipe lengths, fittings and upstream
supply.
"""

from __future__ import annotations

from math import pi, sqrt


def hydraulic_reference_flow_lph(
    nominal_diameter_mm: float,
    static_pressure_bar: float,
) -> float:
    """Return a conservative fault-flow plausibility reference in L/h.

    The model uses nominal cross-sectional area and a pressure-scaled practical
    velocity envelope. It is intentionally bounded and must not be treated as a
    theoretical maximum.
    """
    diameter_m = max(1.0, float(nominal_diameter_mm)) / 1000.0
    pressure_bar = max(0.1, float(static_pressure_bar))
    area_m2 = pi * diameter_m**2 / 4.0

    # Around 3 m/s is already high for normal residential operation. A pipe
    # failure can exceed that, so the reference scales with sqrt(pressure) and
    # is bounded to keep the heuristic plausible rather than idealized.
    velocity_m_s = 3.0 * sqrt(pressure_bar / 3.0)
    velocity_m_s = min(6.0, max(1.5, velocity_m_s))

    return area_m2 * velocity_m_s * 3600.0 * 1000.0
