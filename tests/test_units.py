"""Tests for unit normalization."""

import pytest

from custom_components.water_leak_detection.units import (
    UnsupportedUnitError,
    normalize_flow_lph,
    normalize_volume_l,
)


def test_flow_m3_h_to_l_h() -> None:
    assert normalize_flow_lph(0.007, "m³/h") == pytest.approx(7.0)


def test_flow_l_min_to_l_h() -> None:
    assert normalize_flow_lph(2.5, "L/min") == pytest.approx(150.0)


def test_volume_m3_to_l() -> None:
    assert normalize_volume_l(1.234, "m³") == pytest.approx(1234.0)


def test_unsupported_flow_unit() -> None:
    with pytest.raises(UnsupportedUnitError):
        normalize_flow_lph(1.0, "W")
