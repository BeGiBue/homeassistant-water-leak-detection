"""Sensors for Home Assistant Water Leak Detection."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime, UnitOfVolume, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DetectorKind
from .entity import WaterLeakEntity
from .manager import WaterLeakManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Water Leak Detection sensors."""
    manager: WaterLeakManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WaterLeakStatusSensor(manager),
            CurrentFlowSensor(manager),
            ActiveEventDurationSensor(manager),
            ActiveEventVolumeSensor(manager),
            BypassRemainingSensor(manager),
        ]
    )


class WaterLeakStatusSensor(WaterLeakEntity, SensorEntity):
    """Overall detector state."""

    _attr_name = "Status"
    _attr_icon = "mdi:water-alert"

    def __init__(self, manager: WaterLeakManager) -> None:
        super().__init__(manager, "status")

    @property
    def native_value(self) -> str:
        if not self.manager.source_available:
            return "source_unavailable"
        return self.manager.engine.snapshot(self.manager.current_total_l).status

    @property
    def extra_state_attributes(self):
        snapshot = self.manager.engine.snapshot(self.manager.current_total_l)
        return {
            "flow_source": self.manager.flow_entity_id,
            "total_source": self.manager.total_entity_id,
            "source_available": self.manager.source_available,
            "active_event_id": snapshot.active_event_id,
            "active_detector": snapshot.active_kind.value
            if snapshot.active_kind
            else None,
            "high_flow_bypass": self.manager.high_flow_bypass_active,
            "detectors": {
                kind.value: self.manager.engine.runtimes[kind].phase.value
                for kind in DetectorKind
            },
        }


class CurrentFlowSensor(WaterLeakEntity, SensorEntity):
    """Normalized source flow."""

    _attr_name = "Current flow"
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_HOUR
    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-pump"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 1

    def __init__(self, manager: WaterLeakManager) -> None:
        super().__init__(manager, "current_flow")

    @property
    def available(self) -> bool:
        return (
            self.manager.source_available
            and self.manager.current_flow_lph is not None
        )

    @property
    def native_value(self) -> float | None:
        return self.manager.current_flow_lph


class ActiveEventDurationSensor(WaterLeakEntity, SensorEntity):
    """Duration of the highest priority active event."""

    _attr_name = "Active event duration"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-alert-outline"

    def __init__(self, manager: WaterLeakManager) -> None:
        super().__init__(manager, "active_event_duration")

    @property
    def native_value(self) -> int:
        snapshot = self.manager.engine.snapshot(self.manager.current_total_l)
        if snapshot.active_started_at is None:
            return 0
        return max(
            0,
            int(
                (dt_util.utcnow() - snapshot.active_started_at).total_seconds()
            ),
        )


class ActiveEventVolumeSensor(WaterLeakEntity, SensorEntity):
    """Water volume used since the highest priority event started."""

    _attr_name = "Active event volume"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_icon = "mdi:water-plus"
    _attr_suggested_display_precision = 1

    def __init__(self, manager: WaterLeakManager) -> None:
        super().__init__(manager, "active_event_volume")

    @property
    def native_value(self) -> float:
        return round(
            self.manager.engine.snapshot(
                self.manager.current_total_l
            ).active_volume_l,
            2,
        )


class BypassRemainingSensor(WaterLeakEntity, SensorEntity):
    """Remaining High Flow bypass time."""

    _attr_name = "High flow bypass remaining"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-sand"

    def __init__(self, manager: WaterLeakManager) -> None:
        super().__init__(manager, "high_flow_bypass_remaining")

    @property
    def native_value(self) -> int:
        return self.manager.bypass_remaining_seconds

    @property
    def extra_state_attributes(self):
        return {
            "active": self.manager.high_flow_bypass_active,
            "finishes_at": self.manager.bypass_until.isoformat()
            if self.manager.bypass_until
            else None,
        }
