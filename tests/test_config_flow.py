"""Tests for expert option validation."""

from custom_components.water_leak_detection.config_flow import WaterLeakOptionsFlow
from custom_components.water_leak_detection.const import (
    CONF_BURST_RESET_LPH,
    CONF_BURST_THRESHOLD_LPH,
    CONF_HIGH_QUIET_LPH,
    CONF_HIGH_THRESHOLD_LPH,
    CONF_LOW_QUIET_LPH,
    CONF_LOW_THRESHOLD_LPH,
    CONF_SLOW_THRESHOLD_LPH,
)


def _valid_values() -> dict[str, float]:
    return {
        CONF_SLOW_THRESHOLD_LPH: 3.0,
        CONF_LOW_THRESHOLD_LPH: 150.0,
        CONF_LOW_QUIET_LPH: 20.0,
        CONF_HIGH_THRESHOLD_LPH: 600.0,
        CONF_HIGH_QUIET_LPH: 100.0,
        CONF_BURST_THRESHOLD_LPH: 2000.0,
        CONF_BURST_RESET_LPH: 500.0,
    }


def test_expert_threshold_order_is_valid() -> None:
    assert WaterLeakOptionsFlow._validate_expert_options(_valid_values()) == {}


def test_expert_threshold_order_rejected() -> None:
    values = _valid_values()
    values[CONF_LOW_THRESHOLD_LPH] = 700.0

    assert WaterLeakOptionsFlow._validate_expert_options(values) == {
        "base": "invalid_threshold_order"
    }


def test_low_quiet_threshold_must_be_below_low_start() -> None:
    values = _valid_values()
    values[CONF_LOW_QUIET_LPH] = values[CONF_LOW_THRESHOLD_LPH]

    assert WaterLeakOptionsFlow._validate_expert_options(values) == {
        "base": "invalid_low_quiet_threshold"
    }


def test_high_quiet_threshold_must_be_below_high_start() -> None:
    values = _valid_values()
    values[CONF_HIGH_QUIET_LPH] = values[CONF_HIGH_THRESHOLD_LPH]

    assert WaterLeakOptionsFlow._validate_expert_options(values) == {
        "base": "invalid_high_quiet_threshold"
    }


def test_burst_reset_must_be_below_burst_start() -> None:
    values = _valid_values()
    values[CONF_BURST_RESET_LPH] = values[CONF_BURST_THRESHOLD_LPH]

    assert WaterLeakOptionsFlow._validate_expert_options(values) == {
        "base": "invalid_burst_reset_threshold"
    }
