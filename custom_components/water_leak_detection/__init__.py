"""Home Assistant Water Leak Detection integration."""

from __future__ import annotations

import logging

import probatio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import translation

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DURATION_MINUTES,
    DOMAIN,
    NAME,
    PLATFORMS,
    SERVICE_CANCEL_HIGH_FLOW_BYPASS,
    SERVICE_RESET_LEARNING,
    SERVICE_START_HIGH_FLOW_BYPASS,
)
from .manager import WaterLeakManager

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _manager_for_call(hass: HomeAssistant, call: ServiceCall) -> WaterLeakManager:
    managers: dict[str, WaterLeakManager] = hass.data.get(DOMAIN, {})
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    if entry_id:
        manager = managers.get(entry_id)
        if manager is None:
            raise HomeAssistantError(
                f"Unknown Water Leak Detection config entry: {entry_id}"
            )
        return manager
    if len(managers) == 1:
        return next(iter(managers.values()))
    if not managers:
        raise HomeAssistantError("No Water Leak Detection config entry is loaded")
    raise HomeAssistantError(
        "Multiple Water Leak Detection entries are loaded; config_entry_id is required"
    )


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Set up integration-level actions."""
    hass.data.setdefault(DOMAIN, {})

    async def _start_bypass(call: ServiceCall) -> None:
        manager = _manager_for_call(hass, call)
        duration = call.data.get(ATTR_DURATION_MINUTES)
        await manager.async_start_bypass(
            float(duration) if duration is not None else None
        )

    async def _cancel_bypass(call: ServiceCall) -> None:
        manager = _manager_for_call(hass, call)
        await manager.async_cancel_bypass()

    async def _reset_learning(call: ServiceCall) -> None:
        manager = _manager_for_call(hass, call)
        await manager.async_reset_learning()

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_HIGH_FLOW_BYPASS,
        _start_bypass,
        schema=probatio.Schema(
            {
                probatio.Optional(ATTR_CONFIG_ENTRY_ID): str,
                probatio.Optional(ATTR_DURATION_MINUTES): probatio.All(
                    probatio.Coerce(float), probatio.Range(min=1, max=1440)
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_HIGH_FLOW_BYPASS,
        _cancel_bypass,
        schema=probatio.Schema({probatio.Optional(ATTR_CONFIG_ENTRY_ID): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_LEARNING,
        _reset_learning,
        schema=probatio.Schema({probatio.Optional(ATTR_CONFIG_ENTRY_ID): str}),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one configured water meter."""
    if entry.title == NAME:
        translations = await translation.async_get_translations(
            hass,
            hass.config.language,
            "title",
            [DOMAIN],
        )
        localized_title = translations.get(f"component.{DOMAIN}.title", NAME)
        if localized_title != entry.title:
            hass.config_entries.async_update_entry(entry, title=localized_title)

    manager = WaterLeakManager(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    await manager.async_setup()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a configured water meter."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    manager: WaterLeakManager = hass.data[DOMAIN].pop(entry.entry_id)
    await manager.async_unload()
    return True
