"""Config flow for Home Assistant Water Leak Detection."""

from __future__ import annotations

from typing import Any

import probatio
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    DeviceSelector,
    DeviceSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_BURST_DETECTION_SEC,
    CONF_BURST_RESET_LPH,
    CONF_BURST_RESET_SEC,
    CONF_BURST_THRESHOLD_LPH,
    CONF_BYPASS_DEFAULT_MIN,
    CONF_FLOW_ENTITY,
    CONF_HIGH_DETECTION_MIN,
    CONF_HIGH_QUIET_LPH,
    CONF_HIGH_RESET_MIN,
    CONF_HIGH_THRESHOLD_LPH,
    CONF_HIGH_VOLUME_L,
    CONF_LOW_DETECTION_MIN,
    CONF_LOW_QUIET_LPH,
    CONF_LOW_RESET_MIN,
    CONF_LOW_THRESHOLD_LPH,
    CONF_SHUTOFF_BURST,
    CONF_SHUTOFF_HIGH,
    CONF_SHUTOFF_LOW,
    CONF_SHUTOFF_SLOW,
    CONF_SLOW_DETECTION_MIN,
    CONF_SLOW_RESET_MIN,
    CONF_SLOW_THRESHOLD_LPH,
    CONF_SOURCE_DEVICE,
    CONF_SOURCE_MODE,
    CONF_TOTAL_ENTITY,
    DEFAULT_BURST_DETECTION_SEC,
    DEFAULT_BURST_RESET_LPH,
    DEFAULT_BURST_RESET_SEC,
    DEFAULT_BURST_THRESHOLD_LPH,
    DEFAULT_BYPASS_DEFAULT_MIN,
    DEFAULT_HIGH_DETECTION_MIN,
    DEFAULT_HIGH_QUIET_LPH,
    DEFAULT_HIGH_RESET_MIN,
    DEFAULT_HIGH_THRESHOLD_LPH,
    DEFAULT_HIGH_VOLUME_L,
    DEFAULT_LOW_DETECTION_MIN,
    DEFAULT_LOW_QUIET_LPH,
    DEFAULT_LOW_RESET_MIN,
    DEFAULT_LOW_THRESHOLD_LPH,
    DEFAULT_SHUTOFF_BURST,
    DEFAULT_SHUTOFF_HIGH,
    DEFAULT_SHUTOFF_LOW,
    DEFAULT_SHUTOFF_SLOW,
    DEFAULT_SLOW_DETECTION_MIN,
    DEFAULT_SLOW_RESET_MIN,
    DEFAULT_SLOW_THRESHOLD_LPH,
    DOMAIN,
    NAME,
)
from .units import is_supported_flow_unit, is_supported_volume_unit

SOURCE_ENTITIES = "entities"
SOURCE_DEVICE = "device"
NO_TOTAL = "__none__"


def _number(minimum: float, maximum: float, step: float, unit: str):
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            unit_of_measurement=unit,
            mode=NumberSelectorMode.BOX,
        )
    )


class WaterLeakConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configuration."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._source_device: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose whether data sources are selected by entities or by device."""
        if user_input is not None:
            if user_input[CONF_SOURCE_MODE] == SOURCE_DEVICE:
                return await self.async_step_device()
            return await self.async_step_entities()

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_SOURCE_MODE, default=SOURCE_ENTITIES
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=SOURCE_ENTITIES,
                                    label="Individual entities",
                                ),
                                SelectOptionDict(
                                    value=SOURCE_DEVICE,
                                    label="Home Assistant device",
                                ),
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select source entities directly."""
        errors: dict[str, str] = {}
        if user_input is not None:
            flow_entity = user_input[CONF_FLOW_ENTITY]
            total_entity = user_input.get(CONF_TOTAL_ENTITY) or None
            errors = self._validate_sources(flow_entity, total_entity)
            if not errors:
                return self._create_source_entry(flow_entity, total_entity, None)

        return self.async_show_form(
            step_id="entities",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_FLOW_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain="sensor", multiple=False)
                    ),
                    probatio.Optional(CONF_TOTAL_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain="sensor", multiple=False)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a HA device and discover compatible source entities on it."""
        if user_input is not None:
            self._source_device = user_input[CONF_SOURCE_DEVICE]
            return await self.async_step_device_entities()

        return self.async_show_form(
            step_id="device",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_SOURCE_DEVICE): DeviceSelector(
                        DeviceSelectorConfig()
                    )
                }
            ),
        )

    async def async_step_device_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm compatible sensors discovered on the selected device."""
        if self._source_device is None:
            return await self.async_step_device()

        flow_candidates, total_candidates = self._device_candidates(
            self._source_device
        )
        if not flow_candidates:
            return self.async_abort(reason="device_has_no_flow_sensor")

        errors: dict[str, str] = {}
        if user_input is not None:
            flow_entity = user_input[CONF_FLOW_ENTITY]
            total_raw = user_input.get(CONF_TOTAL_ENTITY, NO_TOTAL)
            total_entity = None if total_raw == NO_TOTAL else total_raw
            errors = self._validate_sources(flow_entity, total_entity)
            if not errors:
                return self._create_source_entry(
                    flow_entity, total_entity, self._source_device
                )

        flow_options = [
            SelectOptionDict(
                value=entity_id,
                label=self._entity_label(entity_id),
            )
            for entity_id in flow_candidates
        ]
        total_options = [
            SelectOptionDict(value=NO_TOTAL, label="No total sensor")
        ]
        total_options.extend(
            SelectOptionDict(
                value=entity_id,
                label=self._entity_label(entity_id),
            )
            for entity_id in total_candidates
        )

        return self.async_show_form(
            step_id="device_entities",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_FLOW_ENTITY,
                        default=flow_candidates[0],
                    ): SelectSelector(
                        SelectSelectorConfig(options=flow_options)
                    ),
                    probatio.Required(
                        CONF_TOTAL_ENTITY,
                        default=NO_TOTAL,
                    ): SelectSelector(
                        SelectSelectorConfig(options=total_options)
                    ),
                }
            ),
            errors=errors,
        )

    def _device_candidates(
        self, device_id: str
    ) -> tuple[list[str], list[str]]:
        registry = er.async_get(self.hass)
        flow: list[str] = []
        total: list[str] = []
        for entry in er.async_entries_for_device(registry, device_id):
            if entry.domain != "sensor" or entry.disabled_by is not None:
                continue
            state = self.hass.states.get(entry.entity_id)
            if state is None:
                continue
            unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            if is_supported_flow_unit(unit):
                flow.append(entry.entity_id)
            if is_supported_volume_unit(unit):
                total.append(entry.entity_id)
        return sorted(flow), sorted(total)

    def _entity_label(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        if state is None:
            return entity_id
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        return f"{state.name} ({unit})" if unit else state.name

    def _validate_sources(
        self, flow_entity: str, total_entity: str | None
    ) -> dict[str, str]:
        errors: dict[str, str] = {}
        flow_state = self.hass.states.get(flow_entity)
        if flow_state is None:
            errors[CONF_FLOW_ENTITY] = "entity_not_available"
        elif not is_supported_flow_unit(
            flow_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        ):
            errors[CONF_FLOW_ENTITY] = "unsupported_flow_unit"

        if total_entity:
            total_state = self.hass.states.get(total_entity)
            if total_state is None:
                errors[CONF_TOTAL_ENTITY] = "entity_not_available"
            elif not is_supported_volume_unit(
                total_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            ):
                errors[CONF_TOTAL_ENTITY] = "unsupported_volume_unit"
            elif total_entity == flow_entity:
                errors[CONF_TOTAL_ENTITY] = "same_source_entity"
        return errors

    def _create_source_entry(
        self,
        flow_entity: str,
        total_entity: str | None,
        device_id: str | None,
    ) -> ConfigFlowResult:
        for entry in self._async_current_entries():
            if entry.data.get(CONF_FLOW_ENTITY) == flow_entity:
                return self.async_abort(reason="already_configured")

        data: dict[str, Any] = {CONF_FLOW_ENTITY: flow_entity}
        if total_entity:
            data[CONF_TOTAL_ENTITY] = total_entity
        if device_id:
            data[CONF_SOURCE_DEVICE] = device_id
        return self.async_create_entry(title=NAME, data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create options flow."""
        return WaterLeakOptionsFlow()


class WaterLeakOptionsFlow(OptionsFlow):
    """Expert detector settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit expert settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_expert_options(user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        values = user_input if user_input is not None else options
        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_SLOW_THRESHOLD_LPH,
                    default=values.get(
                        CONF_SLOW_THRESHOLD_LPH,
                        DEFAULT_SLOW_THRESHOLD_LPH,
                    ),
                ): _number(1, 500, 1, "L/h"),
                probatio.Required(
                    CONF_SLOW_DETECTION_MIN,
                    default=values.get(
                        CONF_SLOW_DETECTION_MIN,
                        DEFAULT_SLOW_DETECTION_MIN,
                    ),
                ): _number(1, 1440, 1, "min"),
                probatio.Required(
                    CONF_SLOW_RESET_MIN,
                    default=values.get(
                        CONF_SLOW_RESET_MIN,
                        DEFAULT_SLOW_RESET_MIN,
                    ),
                ): _number(1, 180, 1, "min"),
                probatio.Required(
                    CONF_LOW_THRESHOLD_LPH,
                    default=values.get(
                        CONF_LOW_THRESHOLD_LPH,
                        DEFAULT_LOW_THRESHOLD_LPH,
                    ),
                ): _number(1, 5000, 1, "L/h"),
                probatio.Required(
                    CONF_LOW_DETECTION_MIN,
                    default=values.get(
                        CONF_LOW_DETECTION_MIN,
                        DEFAULT_LOW_DETECTION_MIN,
                    ),
                ): _number(1, 1440, 1, "min"),
                probatio.Required(
                    CONF_LOW_QUIET_LPH,
                    default=values.get(
                        CONF_LOW_QUIET_LPH,
                        DEFAULT_LOW_QUIET_LPH,
                    ),
                ): _number(0, 1000, 1, "L/h"),
                probatio.Required(
                    CONF_LOW_RESET_MIN,
                    default=values.get(
                        CONF_LOW_RESET_MIN,
                        DEFAULT_LOW_RESET_MIN,
                    ),
                ): _number(1, 180, 1, "min"),
                probatio.Required(
                    CONF_HIGH_THRESHOLD_LPH,
                    default=values.get(
                        CONF_HIGH_THRESHOLD_LPH,
                        DEFAULT_HIGH_THRESHOLD_LPH,
                    ),
                ): _number(1, 10000, 10, "L/h"),
                probatio.Required(
                    CONF_HIGH_DETECTION_MIN,
                    default=values.get(
                        CONF_HIGH_DETECTION_MIN,
                        DEFAULT_HIGH_DETECTION_MIN,
                    ),
                ): _number(1, 1440, 1, "min"),
                probatio.Required(
                    CONF_HIGH_VOLUME_L,
                    default=values.get(
                        CONF_HIGH_VOLUME_L,
                        DEFAULT_HIGH_VOLUME_L,
                    ),
                ): _number(1, 50000, 10, "L"),
                probatio.Required(
                    CONF_HIGH_QUIET_LPH,
                    default=values.get(
                        CONF_HIGH_QUIET_LPH,
                        DEFAULT_HIGH_QUIET_LPH,
                    ),
                ): _number(0, 5000, 10, "L/h"),
                probatio.Required(
                    CONF_HIGH_RESET_MIN,
                    default=values.get(
                        CONF_HIGH_RESET_MIN,
                        DEFAULT_HIGH_RESET_MIN,
                    ),
                ): _number(1, 180, 1, "min"),
                probatio.Required(
                    CONF_BURST_THRESHOLD_LPH,
                    default=values.get(
                        CONF_BURST_THRESHOLD_LPH,
                        DEFAULT_BURST_THRESHOLD_LPH,
                    ),
                ): _number(100, 50000, 10, "L/h"),
                probatio.Required(
                    CONF_BURST_DETECTION_SEC,
                    default=values.get(
                        CONF_BURST_DETECTION_SEC,
                        DEFAULT_BURST_DETECTION_SEC,
                    ),
                ): _number(1, 600, 1, "s"),
                probatio.Required(
                    CONF_BURST_RESET_LPH,
                    default=values.get(
                        CONF_BURST_RESET_LPH,
                        DEFAULT_BURST_RESET_LPH,
                    ),
                ): _number(0, 10000, 10, "L/h"),
                probatio.Required(
                    CONF_BURST_RESET_SEC,
                    default=values.get(
                        CONF_BURST_RESET_SEC,
                        DEFAULT_BURST_RESET_SEC,
                    ),
                ): _number(1, 1800, 1, "s"),
                probatio.Required(
                    CONF_BYPASS_DEFAULT_MIN,
                    default=values.get(
                        CONF_BYPASS_DEFAULT_MIN,
                        DEFAULT_BYPASS_DEFAULT_MIN,
                    ),
                ): _number(1, 1440, 1, "min"),
                probatio.Required(
                    CONF_SHUTOFF_SLOW,
                    default=values.get(
                        CONF_SHUTOFF_SLOW,
                        DEFAULT_SHUTOFF_SLOW,
                    ),
                ): BooleanSelector(),
                probatio.Required(
                    CONF_SHUTOFF_LOW,
                    default=values.get(
                        CONF_SHUTOFF_LOW,
                        DEFAULT_SHUTOFF_LOW,
                    ),
                ): BooleanSelector(),
                probatio.Required(
                    CONF_SHUTOFF_HIGH,
                    default=values.get(
                        CONF_SHUTOFF_HIGH,
                        DEFAULT_SHUTOFF_HIGH,
                    ),
                ): BooleanSelector(),
                probatio.Required(
                    CONF_SHUTOFF_BURST,
                    default=values.get(
                        CONF_SHUTOFF_BURST,
                        DEFAULT_SHUTOFF_BURST,
                    ),
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    def _validate_expert_options(values: dict[str, Any]) -> dict[str, str]:
        """Validate relationships between expert thresholds."""
        slow = float(values[CONF_SLOW_THRESHOLD_LPH])
        low = float(values[CONF_LOW_THRESHOLD_LPH])
        high = float(values[CONF_HIGH_THRESHOLD_LPH])
        burst = float(values[CONF_BURST_THRESHOLD_LPH])
        if not slow < low < high < burst:
            return {"base": "invalid_threshold_order"}
        if float(values[CONF_LOW_QUIET_LPH]) >= low:
            return {"base": "invalid_low_quiet_threshold"}
        if float(values[CONF_HIGH_QUIET_LPH]) >= high:
            return {"base": "invalid_high_quiet_threshold"}
        if float(values[CONF_BURST_RESET_LPH]) >= burst:
            return {"base": "invalid_burst_reset_threshold"}
        return {}
