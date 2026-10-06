"""Tests for expert option validation."""

from custom_components.water_leak_detection.config_flow import (
    WaterLeakOptionsFlow,
    _recipient_description_placeholders,
)
from custom_components.water_leak_detection.const import (
    RECIPIENT_NAME,
    RECIPIENT_NOTIFY_SERVICE,
    RECIPIENT_TRACKER_ENTITY,
    CONF_BURST_LEARNED_MULTIPLIER,
    CONF_BURST_RESET_LPH,
    CONF_BURST_THRESHOLD_LPH,
    CONF_HIGH_LEARNED_MULTIPLIER,
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
        CONF_HIGH_LEARNED_MULTIPLIER: 1.2,
        CONF_BURST_LEARNED_MULTIPLIER: 1.8,
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


def test_adaptive_burst_multiplier_must_exceed_high_multiplier() -> None:
    values = _valid_values()
    values[CONF_HIGH_LEARNED_MULTIPLIER] = 2.0
    values[CONF_BURST_LEARNED_MULTIPLIER] = 1.8

    assert WaterLeakOptionsFlow._validate_expert_options(values) == {
        "base": "invalid_adaptive_multiplier_order"
    }


def test_recipient_overview_lists_all_configured_devices() -> None:
    recipients = [
        {
            RECIPIENT_NAME: "Phone",
            RECIPIENT_NOTIFY_SERVICE: "notify.mobile_app_phone",
            RECIPIENT_TRACKER_ENTITY: "device_tracker.phone",
        },
        {
            RECIPIENT_NAME: "Tablet",
            RECIPIENT_NOTIFY_SERVICE: "notify.mobile_app_tablet",
            RECIPIENT_TRACKER_ENTITY: "device_tracker.tablet",
        },
    ]

    placeholders = _recipient_description_placeholders(recipients)

    assert placeholders["recipient_count"] == "2"
    assert "Phone · notify.mobile_app_phone · device_tracker.phone" in placeholders[
        "configured_recipients"
    ]
    assert "Tablet · notify.mobile_app_tablet · device_tracker.tablet" in placeholders[
        "configured_recipients"
    ]


def test_recipient_overview_handles_empty_list() -> None:
    assert _recipient_description_placeholders([]) == {
        "recipient_count": "0",
        "configured_recipients": "—",
    }
