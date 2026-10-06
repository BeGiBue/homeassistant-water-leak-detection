"""Tests for the hydraulic plausibility model."""

import pytest

from custom_components.water_leak_detection.hydraulic import hydraulic_reference_flow_lph


def test_dn25_at_3_5_bar_is_residential_plausibility_range() -> None:
    value = hydraulic_reference_flow_lph(25.0, 3.5)
    assert 5000 < value < 6500


def test_larger_pipe_has_much_higher_reference_flow() -> None:
    dn25 = hydraulic_reference_flow_lph(25.0, 3.5)
    dn32 = hydraulic_reference_flow_lph(32.0, 3.5)
    assert dn32 > dn25 * 1.5


def test_pressure_increases_reference_sublinearly() -> None:
    low = hydraulic_reference_flow_lph(25.0, 2.0)
    high = hydraulic_reference_flow_lph(25.0, 8.0)
    assert high > low
    assert high < low * 4
