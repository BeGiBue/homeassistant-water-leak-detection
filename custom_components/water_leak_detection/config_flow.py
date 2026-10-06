"""Config flow for Water Leak Guard."""

from __future__ import annotations

from secrets import token_urlsafe
from typing import Any
from uuid import uuid4

import probatio
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import translation
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
    TextSelector,
)

from .const import (
    CONF_BURST_DETECTION_SEC,
    CONF_BURST_LEARNED_MULTIPLIER,
    CONF_BURST_RATE_CONFIRM_SEC,
    CONF_BURST_RATE_RISE_LPH_10S,
    CONF_BURST_RESET_LPH,
    CONF_BURST_RESET_SEC,
    CONF_BURST_THRESHOLD_LPH,
    CONF_BYPASS_DEFAULT_MIN,
    CONF_FLOW_ENTITY,
    CONF_HIGH_DETECTION_MIN,
    CONF_HIGH_LEARNED_MULTIPLIER,
    CONF_HIGH_QUIET_LPH,
    CONF_HIGH_RESET_MIN,
    CONF_HIGH_THRESHOLD_LPH,
    CONF_HIGH_VOLUME_L,
    CONF_HYDRAULIC_BURST_FRACTION,
    CONF_LEARNING_WINDOW_DAYS,
    CONF_LOW_DETECTION_MIN,
    CONF_LOW_QUIET_LPH,
    CONF_LOW_RESET_MIN,
    CONF_LOW_THRESHOLD_LPH,
    CONF_MANUAL_MAX_FLOW_LPH,
    CONF_NOTIFICATION_RECIPIENTS,
    CONF_PIPE_DIAMETER_MM,
    CONF_SHUTOFF_BURST,
    CONF_SHUTOFF_HIGH,
    CONF_SHUTOFF_LOW,
    CONF_SHUTOFF_SLOW,
    CONF_SLOW_DETECTION_MIN,
    CONF_SLOW_RESET_MIN,
    CONF_SLOW_THRESHOLD_LPH,
    CONF_SOURCE_DEVICE,
    CONF_SOURCE_MODE,
    CONF_STATIC_PRESSURE_BAR,
    CONF_TOTAL_ENTITY,
    DEFAULT_BURST_DETECTION_SEC,
    DEFAULT_BURST_LEARNED_MULTIPLIER,
    DEFAULT_BURST_RATE_CONFIRM_SEC,
    DEFAULT_BURST_RATE_RISE_LPH_10S,
    DEFAULT_BURST_RESET_LPH,
    DEFAULT_BURST_RESET_SEC,
    DEFAULT_BURST_THRESHOLD_LPH,
    DEFAULT_BYPASS_DEFAULT_MIN,
    DEFAULT_HIGH_DETECTION_MIN,
    DEFAULT_HIGH_LEARNED_MULTIPLIER,
    DEFAULT_HIGH_QUIET_LPH,
    DEFAULT_HIGH_RESET_MIN,
    DEFAULT_HIGH_THRESHOLD_LPH,
    DEFAULT_HIGH_VOLUME_L,
    DEFAULT_HYDRAULIC_BURST_FRACTION,
    DEFAULT_LEARNING_WINDOW_DAYS,
    DEFAULT_LOW_DETECTION_MIN,
    DEFAULT_LOW_QUIET_LPH,
    DEFAULT_LOW_RESET_MIN,
    DEFAULT_LOW_THRESHOLD_LPH,
    DEFAULT_MANUAL_MAX_FLOW_LPH,
    DEFAULT_PIPE_DIAMETER_MM,
    DEFAULT_SHUTOFF_BURST,
    DEFAULT_SHUTOFF_HIGH,
    DEFAULT_SHUTOFF_LOW,
    DEFAULT_SHUTOFF_SLOW,
    DEFAULT_SLOW_DETECTION_MIN,
    DEFAULT_SLOW_RESET_MIN,
    DEFAULT_SLOW_THRESHOLD_LPH,
    DEFAULT_STATIC_PRESSURE_BAR,
    DOMAIN,
    NAME,
    RECIPIENT_ALLOW_GLOBAL_ACK,
    RECIPIENT_CRITICAL_ENABLED,
    RECIPIENT_ID,
    RECIPIENT_NAME,
    RECIPIENT_NOTIFY_SERVICE,
    RECIPIENT_TOKEN,
    RECIPIENT_TRACKER_ENTITY,
    RECIPIENT_TRUSTED_STATIONARY,
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


def _recipient_description_placeholders(
    recipients: list[dict[str, Any]],
) -> dict[str, str]:
    """Build a safe, human-readable overview of configured recipients."""
    valid = [recipient for recipient in recipients if isinstance(recipient, dict)]
    if not valid:
        return {
            "recipient_count": "0",
            "configured_recipients": "—",
        }

    lines = [
        f"- **{str(recipient.get(RECIPIENT_NAME) or '—')}**"
        for recipient in valid
    ]

    return {
        "recipient_count": str(len(valid)),
        "configured_recipients": "\n".join(lines),
    }


class WaterLeakConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configuration."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._source_device: str | None = None
        self._entry_data: dict[str, Any] = {}
        self._initial_recipients: list[dict[str, Any]] = []

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
                            options=[SOURCE_ENTITIES, SOURCE_DEVICE],
                            translation_key=CONF_SOURCE_MODE,
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
                return await self._prepare_source_entry(
                    flow_entity, total_entity, None
                )

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
                return await self._prepare_source_entry(
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
            SelectOptionDict(
                value=entity_id,
                label=self._entity_label(entity_id),
            )
            for entity_id in total_candidates
        ]

        schema: dict[Any, Any] = {
            probatio.Required(
                CONF_FLOW_ENTITY,
                default=flow_candidates[0],
            ): SelectSelector(
                SelectSelectorConfig(options=flow_options)
            )
        }
        if total_options:
            schema[probatio.Optional(CONF_TOTAL_ENTITY)] = SelectSelector(
                SelectSelectorConfig(options=total_options)
            )

        return self.async_show_form(
            step_id="device_entities",
            data_schema=probatio.Schema(schema),
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

    async def _prepare_source_entry(
        self,
        flow_entity: str,
        total_entity: str | None,
        device_id: str | None,
    ) -> ConfigFlowResult:
        """Store source configuration and continue to notification recipients."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_FLOW_ENTITY) == flow_entity:
                return self.async_abort(reason="already_configured")

        self._entry_data = {CONF_FLOW_ENTITY: flow_entity}
        if total_entity:
            self._entry_data[CONF_TOTAL_ENTITY] = total_entity
        if device_id:
            self._entry_data[CONF_SOURCE_DEVICE] = device_id
        return await self.async_step_notifications()

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow notification recipients to be configured during setup."""
        menu_options = ["finish_setup"]
        if self._mobile_notify_services():
            menu_options.insert(0, "add_initial_recipient")
        return self.async_show_menu(
            step_id="notifications",
            menu_options=menu_options,
            description_placeholders=_recipient_description_placeholders(
                self._initial_recipients
            ),
        )

    async def async_step_add_initial_recipient(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add one Companion recipient during initial setup."""
        notify_services = self._mobile_notify_services()
        if not notify_services:
            return await self.async_step_notifications()

        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input[RECIPIENT_NAME]).strip()
            notify_service = str(user_input[RECIPIENT_NOTIFY_SERVICE])
            if not name:
                errors["base"] = "recipient_name_required"
            elif any(
                raw.get(RECIPIENT_NOTIFY_SERVICE) == notify_service
                for raw in self._initial_recipients
            ):
                errors["base"] = "recipient_notify_service_exists"
            else:
                self._initial_recipients.append(
                    {
                        RECIPIENT_ID: uuid4().hex[:10],
                        RECIPIENT_NAME: name,
                        RECIPIENT_NOTIFY_SERVICE: notify_service,
                        RECIPIENT_TRACKER_ENTITY: str(
                            user_input[RECIPIENT_TRACKER_ENTITY]
                        ),
                        RECIPIENT_CRITICAL_ENABLED: bool(
                            user_input[RECIPIENT_CRITICAL_ENABLED]
                        ),
                        RECIPIENT_ALLOW_GLOBAL_ACK: bool(
                            user_input[RECIPIENT_ALLOW_GLOBAL_ACK]
                        ),
                        RECIPIENT_TRUSTED_STATIONARY: bool(
                            user_input[RECIPIENT_TRUSTED_STATIONARY]
                        ),
                        RECIPIENT_TOKEN: token_urlsafe(12),
                    }
                )
                return await self.async_step_notifications()

        return self.async_show_form(
            step_id="add_initial_recipient",
            data_schema=self._recipient_schema(notify_services),
            errors=errors,
            description_placeholders=_recipient_description_placeholders(
                self._initial_recipients
            ),
        )

    async def async_step_finish_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the config entry after source and recipient setup."""
        translations = await translation.async_get_translations(
            self.hass,
            self.hass.config.language,
            "title",
            [DOMAIN],
            config_flow=True,
        )
        title = translations.get(f"component.{DOMAIN}.title", NAME)
        return self.async_create_entry(
            title=title,
            data=self._entry_data,
            options={CONF_NOTIFICATION_RECIPIENTS: self._initial_recipients},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow source sensors to be changed after setup."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            flow_entity = str(user_input[CONF_FLOW_ENTITY])
            total_entity = user_input.get(CONF_TOTAL_ENTITY) or None
            errors = self._validate_sources(flow_entity, total_entity)
            if not errors:
                for current in self._async_current_entries():
                    if (
                        current.entry_id != entry.entry_id
                        and current.data.get(CONF_FLOW_ENTITY) == flow_entity
                    ):
                        return self.async_abort(reason="already_configured")
                data = dict(entry.data)
                data[CONF_FLOW_ENTITY] = flow_entity
                if total_entity:
                    data[CONF_TOTAL_ENTITY] = total_entity
                else:
                    data.pop(CONF_TOTAL_ENTITY, None)
                data.pop(CONF_SOURCE_DEVICE, None)
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_FLOW_ENTITY,
                        default=entry.data[CONF_FLOW_ENTITY],
                    ): EntitySelector(
                        EntitySelectorConfig(domain="sensor", multiple=False)
                    ),
                    probatio.Optional(
                        CONF_TOTAL_ENTITY,
                        default=entry.data.get(CONF_TOTAL_ENTITY),
                    ): EntitySelector(
                        EntitySelectorConfig(domain="sensor", multiple=False)
                    ),
                }
            ),
            errors=errors,
        )

    def _mobile_notify_services(self) -> list[str]:
        """Return currently registered Companion mobile notification services."""
        services = self.hass.services.async_services().get("notify", {})
        return sorted(
            f"notify.{service}"
            for service in services
            if service.startswith("mobile_app_")
        )

    @staticmethod
    def _recipient_schema(
        notify_services: list[str],
        *,
        current: dict[str, Any] | None = None,
    ) -> probatio.Schema:
        """Build the recipient configuration form."""
        current = current or {}
        schema: dict[Any, Any] = {
            probatio.Required(
                RECIPIENT_NAME,
                default=current.get(RECIPIENT_NAME, ""),
            ): TextSelector(),
            probatio.Required(
                RECIPIENT_NOTIFY_SERVICE,
                default=current.get(
                    RECIPIENT_NOTIFY_SERVICE,
                    notify_services[0],
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=service, label=service)
                        for service in notify_services
                    ]
                )
            ),
            probatio.Required(
                RECIPIENT_CRITICAL_ENABLED,
                default=bool(
                    current.get(RECIPIENT_CRITICAL_ENABLED, True)
                ),
            ): BooleanSelector(),
            probatio.Required(
                RECIPIENT_ALLOW_GLOBAL_ACK,
                default=bool(
                    current.get(RECIPIENT_ALLOW_GLOBAL_ACK, True)
                ),
            ): BooleanSelector(),
            probatio.Required(
                RECIPIENT_TRUSTED_STATIONARY,
                default=bool(
                    current.get(RECIPIENT_TRUSTED_STATIONARY, False)
                ),
            ): BooleanSelector(),
        }
        tracker_default = current.get(RECIPIENT_TRACKER_ENTITY)
        tracker_key = (
            probatio.Required(
                RECIPIENT_TRACKER_ENTITY,
                default=tracker_default,
            )
            if tracker_default
            else probatio.Required(RECIPIENT_TRACKER_ENTITY)
        )
        schema[tracker_key] = EntitySelector(
            EntitySelectorConfig(
                domain="device_tracker",
                multiple=False,
            )
        )
        return probatio.Schema(schema)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowWithReload:
        """Create options flow."""
        return WaterLeakOptionsFlow()


class WaterLeakOptionsFlow(OptionsFlowWithReload):
    """Options for detector settings and Companion recipients."""

    def __init__(self) -> None:
        """Initialize options flow state."""
        super().__init__()
        self._editing_recipient_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["sources", "notifications", "expert"],
        )

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit measurement sources from the normal Configure dialog."""
        errors: dict[str, str] = {}
        entry = self.config_entry

        if user_input is not None:
            flow_entity = str(user_input[CONF_FLOW_ENTITY])
            total_entity = user_input.get(CONF_TOTAL_ENTITY) or None
            errors = self._validate_sources(flow_entity, total_entity)

            if not errors:
                for current in self.hass.config_entries.async_entries(DOMAIN):
                    if (
                        current.entry_id != entry.entry_id
                        and current.data.get(CONF_FLOW_ENTITY) == flow_entity
                    ):
                        errors["base"] = "already_configured"
                        break

            if not errors:
                data = dict(entry.data)
                data[CONF_FLOW_ENTITY] = flow_entity
                if total_entity:
                    data[CONF_TOTAL_ENTITY] = total_entity
                else:
                    data.pop(CONF_TOTAL_ENTITY, None)
                data.pop(CONF_SOURCE_DEVICE, None)
                if self.hass.config_entries.async_update_entry(entry, data=data):
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return await self.async_step_init()

        return self.async_show_form(
            step_id="sources",
            last_step=False,
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_FLOW_ENTITY,
                        default=entry.data[CONF_FLOW_ENTITY],
                    ): EntitySelector(
                        EntitySelectorConfig(domain="sensor", multiple=False)
                    ),
                    probatio.Optional(
                        CONF_TOTAL_ENTITY,
                        default=entry.data.get(CONF_TOTAL_ENTITY),
                    ): EntitySelector(
                        EntitySelectorConfig(domain="sensor", multiple=False)
                    ),
                }
            ),
            errors=errors,
        )

    def _validate_sources(
        self,
        flow_entity: str,
        total_entity: str | None,
    ) -> dict[str, str]:
        """Validate measurement sources in the options flow."""
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

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage notification recipients."""
        recipients = self._raw_recipients()
        menu_options = ["add_recipient"]
        if recipients:
            menu_options.extend(["edit_recipient", "remove_recipient"])
        menu_options.append("back_to_main")
        return self.async_show_menu(
            step_id="notifications",
            menu_options=menu_options,
            description_placeholders=_recipient_description_placeholders(
                recipients
            ),
        )

    async def async_step_back_to_main(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Return from a submenu to the main Configure menu."""
        return await self.async_step_init()

    async def async_step_expert(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit expert detector settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate_expert_options(user_input)
            if not errors:
                updated = dict(self.config_entry.options)
                updated.update(user_input)
                self._persist_options(updated)
                return await self.async_step_init()

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
                    CONF_LEARNING_WINDOW_DAYS,
                    default=values.get(
                        CONF_LEARNING_WINDOW_DAYS,
                        DEFAULT_LEARNING_WINDOW_DAYS,
                    ),
                ): _number(7, 90, 1, "d"),
                probatio.Required(
                    CONF_MANUAL_MAX_FLOW_LPH,
                    default=values.get(
                        CONF_MANUAL_MAX_FLOW_LPH,
                        DEFAULT_MANUAL_MAX_FLOW_LPH,
                    ),
                ): _number(0, 50000, 10, "L/h"),
                probatio.Required(
                    CONF_PIPE_DIAMETER_MM,
                    default=values.get(
                        CONF_PIPE_DIAMETER_MM,
                        DEFAULT_PIPE_DIAMETER_MM,
                    ),
                ): _number(10, 100, 1, "mm"),
                probatio.Required(
                    CONF_STATIC_PRESSURE_BAR,
                    default=values.get(
                        CONF_STATIC_PRESSURE_BAR,
                        DEFAULT_STATIC_PRESSURE_BAR,
                    ),
                ): _number(0.5, 12, 0.1, "bar"),
                probatio.Required(
                    CONF_HIGH_LEARNED_MULTIPLIER,
                    default=values.get(
                        CONF_HIGH_LEARNED_MULTIPLIER,
                        DEFAULT_HIGH_LEARNED_MULTIPLIER,
                    ),
                ): _number(1.0, 3.0, 0.05, "×"),
                probatio.Required(
                    CONF_BURST_LEARNED_MULTIPLIER,
                    default=values.get(
                        CONF_BURST_LEARNED_MULTIPLIER,
                        DEFAULT_BURST_LEARNED_MULTIPLIER,
                    ),
                ): _number(1.1, 5.0, 0.05, "×"),
                probatio.Required(
                    CONF_HYDRAULIC_BURST_FRACTION,
                    default=values.get(
                        CONF_HYDRAULIC_BURST_FRACTION,
                        DEFAULT_HYDRAULIC_BURST_FRACTION,
                    ),
                ): _number(0.2, 1.0, 0.05, "×"),
                probatio.Required(
                    CONF_BURST_RATE_RISE_LPH_10S,
                    default=values.get(
                        CONF_BURST_RATE_RISE_LPH_10S,
                        DEFAULT_BURST_RATE_RISE_LPH_10S,
                    ),
                ): _number(100, 20000, 100, "L/h / 10 s"),
                probatio.Required(
                    CONF_BURST_RATE_CONFIRM_SEC,
                    default=values.get(
                        CONF_BURST_RATE_CONFIRM_SEC,
                        DEFAULT_BURST_RATE_CONFIRM_SEC,
                    ),
                ): _number(1, 60, 1, "s"),
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
            step_id="expert",
            last_step=False,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_add_recipient(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add one Companion notification recipient."""
        notify_services = self._mobile_notify_services()
        if not notify_services:
            return self.async_abort(reason="no_mobile_app_notify_services")

        existing = self._raw_recipients()
        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input[RECIPIENT_NAME]).strip()
            notify_service = str(user_input[RECIPIENT_NOTIFY_SERVICE])
            tracker_entity = str(user_input[RECIPIENT_TRACKER_ENTITY])

            if not name:
                errors["base"] = "recipient_name_required"
            elif any(
                raw.get(RECIPIENT_NOTIFY_SERVICE) == notify_service
                for raw in existing
            ):
                errors["base"] = "recipient_notify_service_exists"
            else:
                recipient = {
                    RECIPIENT_ID: uuid4().hex[:10],
                    RECIPIENT_NAME: name,
                    RECIPIENT_NOTIFY_SERVICE: notify_service,
                    RECIPIENT_TRACKER_ENTITY: tracker_entity,
                    RECIPIENT_CRITICAL_ENABLED: bool(
                        user_input[RECIPIENT_CRITICAL_ENABLED]
                    ),
                    RECIPIENT_ALLOW_GLOBAL_ACK: bool(
                        user_input[RECIPIENT_ALLOW_GLOBAL_ACK]
                    ),
                    RECIPIENT_TRUSTED_STATIONARY: bool(
                        user_input[RECIPIENT_TRUSTED_STATIONARY]
                    ),
                    RECIPIENT_TOKEN: token_urlsafe(12),
                }
                updated = dict(self.config_entry.options)
                updated[CONF_NOTIFICATION_RECIPIENTS] = [*existing, recipient]
                self._persist_options(updated)
                return await self.async_step_notifications()

        return self.async_show_form(
            step_id="add_recipient",
            last_step=False,
            data_schema=WaterLeakConfigFlow._recipient_schema(notify_services),
            errors=errors,
            description_placeholders=_recipient_description_placeholders(
                existing
            ),
        )

    async def async_step_edit_recipient(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a configured notification recipient to edit."""
        recipients = self._raw_recipients()
        if not recipients:
            return self.async_abort(reason="no_recipients_configured")

        if user_input is not None:
            self._editing_recipient_id = str(user_input[RECIPIENT_ID])
            return await self.async_step_edit_recipient_details()

        options = [
            SelectOptionDict(
                value=str(raw[RECIPIENT_ID]),
                label=str(raw.get(RECIPIENT_NAME, raw[RECIPIENT_ID])),
            )
            for raw in recipients
            if raw.get(RECIPIENT_ID)
        ]
        return self.async_show_form(
            step_id="edit_recipient",
            last_step=False,
            data_schema=probatio.Schema(
                {
                    probatio.Required(RECIPIENT_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    )
                }
            ),
            description_placeholders=_recipient_description_placeholders(
                recipients
            ),
        )

    async def async_step_edit_recipient_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit one Companion notification recipient."""
        recipient_id = self._editing_recipient_id
        recipients = self._raw_recipients()
        current = next(
            (
                raw
                for raw in recipients
                if str(raw.get(RECIPIENT_ID, "")) == recipient_id
            ),
            None,
        )
        if current is None:
            return self.async_abort(reason="recipient_not_found")

        notify_services = self._mobile_notify_services()
        current_service = str(current.get(RECIPIENT_NOTIFY_SERVICE, ""))
        if current_service and current_service not in notify_services:
            notify_services.append(current_service)
            notify_services.sort()

        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input[RECIPIENT_NAME]).strip()
            notify_service = str(user_input[RECIPIENT_NOTIFY_SERVICE])
            if not name:
                errors["base"] = "recipient_name_required"
            elif any(
                str(raw.get(RECIPIENT_ID, "")) != recipient_id
                and raw.get(RECIPIENT_NOTIFY_SERVICE) == notify_service
                for raw in recipients
            ):
                errors["base"] = "recipient_notify_service_exists"
            else:
                replacement = {
                    RECIPIENT_ID: str(current[RECIPIENT_ID]),
                    RECIPIENT_NAME: name,
                    RECIPIENT_NOTIFY_SERVICE: notify_service,
                    RECIPIENT_TRACKER_ENTITY: str(
                        user_input[RECIPIENT_TRACKER_ENTITY]
                    ),
                    RECIPIENT_CRITICAL_ENABLED: bool(
                        user_input[RECIPIENT_CRITICAL_ENABLED]
                    ),
                    RECIPIENT_ALLOW_GLOBAL_ACK: bool(
                        user_input[RECIPIENT_ALLOW_GLOBAL_ACK]
                    ),
                    RECIPIENT_TRUSTED_STATIONARY: bool(
                        user_input[RECIPIENT_TRUSTED_STATIONARY]
                    ),
                    RECIPIENT_TOKEN: str(current[RECIPIENT_TOKEN]),
                }
                updated = dict(self.config_entry.options)
                updated[CONF_NOTIFICATION_RECIPIENTS] = [
                    replacement
                    if str(raw.get(RECIPIENT_ID, "")) == recipient_id
                    else raw
                    for raw in recipients
                ]
                self._persist_options(updated)
                self._editing_recipient_id = None
                return await self.async_step_notifications()

        return self.async_show_form(
            step_id="edit_recipient_details",
            last_step=False,
            data_schema=WaterLeakConfigFlow._recipient_schema(
                notify_services,
                current=current,
            ),
            errors=errors,
            description_placeholders=_recipient_description_placeholders(
                recipients
            ),
        )

    async def async_step_remove_recipient(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one configured notification recipient."""
        recipients = self._raw_recipients()
        if not recipients:
            return self.async_abort(reason="no_recipients_configured")

        if user_input is not None:
            remove_id = str(user_input[RECIPIENT_ID])
            updated = dict(self.config_entry.options)
            updated[CONF_NOTIFICATION_RECIPIENTS] = [
                raw
                for raw in recipients
                if str(raw.get(RECIPIENT_ID, "")) != remove_id
            ]
            self._persist_options(updated)
            return await self.async_step_notifications()

        options = [
            SelectOptionDict(
                value=str(raw[RECIPIENT_ID]),
                label=str(raw.get(RECIPIENT_NAME, raw[RECIPIENT_ID])),
            )
            for raw in recipients
            if raw.get(RECIPIENT_ID)
        ]
        return self.async_show_form(
            step_id="remove_recipient",
            last_step=False,
            data_schema=probatio.Schema(
                {
                    probatio.Required(RECIPIENT_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    )
                }
            ),
            description_placeholders=_recipient_description_placeholders(
                recipients
            ),
        )

    def _persist_options(self, updated: dict[str, Any]) -> None:
        """Save options immediately while keeping the Configure flow open."""
        if self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=updated,
        ):
            self.hass.config_entries.async_schedule_reload(
                self.config_entry.entry_id
            )

    def _raw_recipients(self) -> list[dict[str, Any]]:
        """Return valid raw recipient option dictionaries."""
        raw = self.config_entry.options.get(CONF_NOTIFICATION_RECIPIENTS, [])
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def _mobile_notify_services(self) -> list[str]:
        """Return currently registered Companion mobile notification services."""
        services = self.hass.services.async_services().get("notify", {})
        return sorted(
            f"notify.{service}"
            for service in services
            if service.startswith("mobile_app_")
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
        high_multiplier = float(values[CONF_HIGH_LEARNED_MULTIPLIER])
        burst_multiplier = float(values[CONF_BURST_LEARNED_MULTIPLIER])
        if burst_multiplier <= high_multiplier:
            return {"base": "invalid_adaptive_multiplier_order"}
        return {}
