"""Tests for expert option validation and Configure flow UX."""

import inspect

from custom_components.water_leak_detection.config_flow import (
    WaterLeakOptionsFlow,
    _recipient_description_placeholders,
)
from custom_components.water_leak_detection.const import (
    CONF_BURST_LEARNED_MULTIPLIER,
    CONF_BURST_RESET_LPH,
    CONF_BURST_THRESHOLD_LPH,
    CONF_HIGH_LEARNED_MULTIPLIER,
    CONF_HIGH_QUIET_LPH,
    CONF_HIGH_THRESHOLD_LPH,
    CONF_LOW_QUIET_LPH,
    CONF_LOW_THRESHOLD_LPH,
    CONF_SLOW_THRESHOLD_LPH,
    RECIPIENT_NAME,
    RECIPIENT_NOTIFY_SERVICE,
    RECIPIENT_TRACKER_ENTITY,
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
    assert placeholders["configured_recipients"] == "- **Phone**\n- **Tablet**"
    assert "notify.mobile_app" not in placeholders["configured_recipients"]
    assert "device_tracker." not in placeholders["configured_recipients"]


def test_recipient_overview_handles_empty_list() -> None:
    assert _recipient_description_placeholders([]) == {
        "recipient_count": "0",
        "configured_recipients": "—",
    }



def test_options_flow_save_steps_do_not_finish_the_flow() -> None:
    """Saving a subsection must return to a menu instead of closing Configure."""
    methods = (
        WaterLeakOptionsFlow.async_step_sources,
        WaterLeakOptionsFlow.async_step_expert,
        WaterLeakOptionsFlow.async_step_add_recipient,
        WaterLeakOptionsFlow.async_step_edit_recipient_details,
        WaterLeakOptionsFlow.async_step_remove_recipient,
    )

    for method in methods:
        source = inspect.getsource(method)
        assert "async_create_entry" not in source

    assert "async_step_init()" in inspect.getsource(
        WaterLeakOptionsFlow.async_step_sources
    )
    assert "async_step_init()" in inspect.getsource(
        WaterLeakOptionsFlow.async_step_expert
    )
    assert "async_step_notifications()" in inspect.getsource(
        WaterLeakOptionsFlow.async_step_add_recipient
    )
    assert "async_step_notifications()" in inspect.getsource(
        WaterLeakOptionsFlow.async_step_edit_recipient_details
    )
    assert "async_step_notifications()" in inspect.getsource(
        WaterLeakOptionsFlow.async_step_remove_recipient
    )


def test_notification_submenu_has_back_navigation() -> None:
    source = inspect.getsource(WaterLeakOptionsFlow.async_step_notifications)
    assert 'menu_options.append("back_to_main")' in source
    assert hasattr(WaterLeakOptionsFlow, "async_step_back_to_main")
