"""Base entity for Water Leak Detection."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .manager import WaterLeakManager


class WaterLeakEntity(Entity):
    """Base entity bound to one Water Leak Detection config entry."""

    _attr_has_entity_name = True

    def __init__(self, manager: WaterLeakManager, key: str) -> None:
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            translation_key="water_leak_detection",
            manufacturer="BeGiBue",
            model="Water Leak Detection",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.manager.async_add_listener(self._handle_manager_update))

    def _handle_manager_update(self) -> None:
        self.async_write_ha_state()
