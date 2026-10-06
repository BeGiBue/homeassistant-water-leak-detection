"""Number entities for Home Assistant Water Leak Detection."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
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
    """Set up bypass duration number."""
    manager: WaterLeakManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HighFlowBypassDurationNumber(manager)])


class HighFlowBypassDurationNumber(WaterLeakEntity, NumberEntity):
    """Default duration used when High Flow bypass is switched on."""

    _attr_name = "High flow bypass duration"
    _attr_icon = "mdi:timer-cog-outline"
    _attr_native_min_value = 1
    _attr_native_max_value = 1440
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX

    def __init__(self, manager: WaterLeakManager) -> None:
        super().__init__(manager, "high_flow_bypass_duration")

    @property
    def native_value(self) -> float:
        return self.manager.bypass_default_minutes

    async def async_set_native_value(self, value: float) -> None:
        await self.manager.async_set_bypass_default_minutes(value)
