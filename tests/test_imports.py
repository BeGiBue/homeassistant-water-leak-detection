"""Import smoke tests for Home Assistant-facing modules."""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "custom_components.water_leak_detection",
        "custom_components.water_leak_detection.binary_sensor",
        "custom_components.water_leak_detection.config_flow",
        "custom_components.water_leak_detection.const",
        "custom_components.water_leak_detection.engine",
        "custom_components.water_leak_detection.entity",
        "custom_components.water_leak_detection.manager",
        "custom_components.water_leak_detection.notifications",
        "custom_components.water_leak_detection.number",
        "custom_components.water_leak_detection.sensor",
        "custom_components.water_leak_detection.switch",
        "custom_components.water_leak_detection.units",
    ],
)
def test_home_assistant_modules_import(module: str) -> None:
    """All integration modules should import against the supported HA release."""
    import_module(module)
