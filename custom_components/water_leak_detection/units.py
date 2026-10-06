"""Unit normalization helpers."""

from __future__ import annotations

from math import isfinite


class UnsupportedUnitError(ValueError):
    """Raised when a source sensor uses an unsupported unit."""


def _clean(unit: str | None) -> str:
    if unit is None:
        raise UnsupportedUnitError("Source entity has no unit of measurement")
    return unit.strip().replace("³", "3").replace(" ", "").lower()


def normalize_flow_lph(value: float, unit: str | None) -> float:
    """Convert a flow value to litres per hour."""
    if not isfinite(value):
        raise ValueError("Flow value must be finite")
    u = _clean(unit)
    factors = {
        "l/h": 1.0,
        "lph": 1.0,
        "l/min": 60.0,
        "l/m": 60.0,
        "l/s": 3600.0,
        "m3/h": 1000.0,
        "m3/min": 60000.0,
        "m3/s": 3_600_000.0,
        "ml/s": 3.6,
        "gal/h": 3.785411784,
        "gal/min": 227.12470704,
        "gal/d": 3.785411784 / 24.0,
        "ft3/min": 1699.01079552,
    }
    try:
        return value * factors[u]
    except KeyError as err:
        raise UnsupportedUnitError(f"Unsupported flow unit: {unit}") from err


def normalize_volume_l(value: float, unit: str | None) -> float:
    """Convert a cumulative volume value to litres."""
    if not isfinite(value):
        raise ValueError("Volume value must be finite")
    u = _clean(unit)
    factors = {
        "l": 1.0,
        "liter": 1.0,
        "litre": 1.0,
        "ml": 0.001,
        "m3": 1000.0,
        "gal": 3.785411784,
        "ft3": 28.316846592,
    }
    try:
        return value * factors[u]
    except KeyError as err:
        raise UnsupportedUnitError(f"Unsupported volume unit: {unit}") from err


def is_supported_flow_unit(unit: str | None) -> bool:
    """Return whether a unit can be normalized as flow."""
    try:
        normalize_flow_lph(1.0, unit)
    except (UnsupportedUnitError, ValueError):
        return False
    return True


def is_supported_volume_unit(unit: str | None) -> bool:
    """Return whether a unit can be normalized as volume."""
    try:
        normalize_volume_l(1.0, unit)
    except (UnsupportedUnitError, ValueError):
        return False
    return True
