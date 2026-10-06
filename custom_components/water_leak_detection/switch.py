"""Switches for Home Assistant Water Leak Detection."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import WaterLeakEntity
from .manager import WaterLeakManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up bypass switch."""
    manager: WaterLeakManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HighFlowBypassSwitch(manager)])


class HighFlowBypassSwitch(WaterLeakEntity, SwitchEntity):
    """Temporarily suppress only High Flow detection."""

    _attr_name = "High flow bypass"
    _attr_icon = "mdi:water-off-outline"

    def __init__(self, manager: WaterLeakManager) -> None:
        super().__init__(manager, "high_flow_bypass")

    @property
    def is_on(self) -> bool:
        return self.manager.high_flow_bypass_active

    async def async_turn_on(self, **kwargs) -> None:
        await self.manager.async_start_bypass()

    async def async_turn_off(self, **kwargs) -> None:
        await self.manager.async_cancel_bypass()

    @property
    def extra_state_attributes(self):
        return {
            "remaining_seconds": self.manager.bypass_remaining_seconds,
            "finishes_at": self.manager.bypass_until.isoformat()
            if self.manager.bypass_until
            else None,
            "burst_leak_protection_active": True,
        }
