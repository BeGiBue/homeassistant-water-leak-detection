"""Runtime manager for Home Assistant Water Leak Detection."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

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
    CONF_LOW_ENABLED,
    CONF_LOW_QUIET_LPH,
    CONF_LOW_RESET_MIN,
    CONF_LOW_THRESHOLD_LPH,
    CONF_SHUTOFF_BURST,
    CONF_SHUTOFF_HIGH,
    CONF_SHUTOFF_LOW,
    CONF_SHUTOFF_SLOW,
    CONF_SLOW_DETECTION_MIN,
    CONF_SLOW_ENABLED,
    CONF_SLOW_RESET_MIN,
    CONF_SLOW_THRESHOLD_LPH,
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
    DEFAULT_LOW_ENABLED,
    DEFAULT_LOW_QUIET_LPH,
    DEFAULT_LOW_RESET_MIN,
    DEFAULT_LOW_THRESHOLD_LPH,
    DEFAULT_SHUTOFF_BURST,
    DEFAULT_SHUTOFF_HIGH,
    DEFAULT_SHUTOFF_LOW,
    DEFAULT_SHUTOFF_SLOW,
    DEFAULT_SLOW_DETECTION_MIN,
    DEFAULT_SLOW_ENABLED,
    DEFAULT_SLOW_RESET_MIN,
    DEFAULT_SLOW_THRESHOLD_LPH,
    EVENT_LEAK_ENDED,
    EVENT_LEAK_STARTED,
    EVENT_SHUTOFF_CLEARED,
    EVENT_SHUTOFF_REQUESTED,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    TICK_SECONDS,
    DetectorPhase,
)
from .engine import DetectionEngine, DetectorSettings, DetectorTransition
from .notifications import NotificationController
from .units import UnsupportedUnitError, normalize_flow_lph, normalize_volume_l

_LOGGER = logging.getLogger(__name__)

Listener = Callable[[], None]


class WaterLeakManager:
    """Coordinate HA source entities, persistence and the pure detector engine."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.flow_entity_id: str = entry.data[CONF_FLOW_ENTITY]
        self.total_entity_id: str | None = entry.data.get(CONF_TOTAL_ENTITY) or None
        self.engine = DetectionEngine(self._settings_from_options())
        self.current_flow_lph: float | None = None
        self.current_total_l: float | None = None
        self.source_available = False
        self.bypass_until = None
        self._listeners: set[Listener] = set()
        self._unsubs: list[Callable[[], None]] = []
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry.entry_id}"
        )
        self._last_shutoff_request = False
        self.notifications = NotificationController(
            hass,
            entry,
            self,
            self._schedule_save,
        )

    async def async_setup(self) -> None:
        """Restore persisted state and start tracking source entities."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            engine_data = stored.get("engine")
            if isinstance(engine_data, dict):
                self.engine.restore(engine_data)
            self.notifications.restore(stored.get("acknowledgements"))
            bypass_until = stored.get("bypass_until")
            if isinstance(bypass_until, str):
                try:
                    parsed = dt_util.parse_datetime(bypass_until)
                except (TypeError, ValueError):
                    parsed = None
                if parsed is not None and parsed > dt_util.utcnow():
                    self.bypass_until = parsed

        self._last_shutoff_request = self.engine.snapshot().shutoff_request
        await self.notifications.async_setup()

        entities = [self.flow_entity_id]
        if self.total_entity_id:
            entities.append(self.total_entity_id)
        self._unsubs.append(
            async_track_state_change_event(self.hass, entities, self._async_source_changed)
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_tick, timedelta(seconds=TICK_SECONDS)
            )
        )
        await self.async_refresh()

    async def async_unload(self) -> None:
        """Stop listeners and save current runtime state."""
        await self.notifications.async_unload()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._store.async_save(self._serialize())

    @callback
    def async_add_listener(self, listener: Listener) -> Callable[[], None]:
        """Register an entity update listener."""
        self._listeners.add(listener)

        @callback
        def _remove() -> None:
            self._listeners.discard(listener)

        return _remove

    @callback
    def _notify_listeners(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    async def _async_source_changed(self, event: Event) -> None:
        await self.async_refresh()

    async def _async_tick(self, _now) -> None:
        await self.async_refresh()

    async def async_refresh(self) -> None:
        """Read source states and evaluate detectors."""
        flow_state = self.hass.states.get(self.flow_entity_id)
        if not self._usable_state(flow_state):
            self.source_available = False
            self.engine.suspend_for_unavailable_source()
            self._schedule_save()
            self._notify_listeners()
            return

        try:
            flow = normalize_flow_lph(
                float(flow_state.state),
                flow_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
            )
        except (TypeError, ValueError, UnsupportedUnitError) as err:
            _LOGGER.warning(
                "Unable to normalize flow source %s: %s", self.flow_entity_id, err
            )
            self.source_available = False
            self.engine.suspend_for_unavailable_source()
            self._schedule_save()
            self._notify_listeners()
            return

        total: float | None = None
        if self.total_entity_id:
            total_state = self.hass.states.get(self.total_entity_id)
            if self._usable_state(total_state):
                try:
                    total = normalize_volume_l(
                        float(total_state.state),
                        total_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
                    )
                except (TypeError, ValueError, UnsupportedUnitError) as err:
                    _LOGGER.debug(
                        "Unable to normalize optional total source %s: %s",
                        self.total_entity_id,
                        err,
                    )

        self.source_available = True
        self.current_flow_lph = flow
        self.current_total_l = total
        now = dt_util.utcnow()
        transitions = self.engine.sample(
            now,
            flow,
            total,
            high_flow_bypassed=self.high_flow_bypass_active,
        )
        self._handle_transitions(transitions)
        self._handle_shutoff_transition()
        self._schedule_save()
        self._notify_listeners()

    @staticmethod
    def _usable_state(state: State | None) -> bool:
        return state is not None and state.state not in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
            "",
        )

    @property
    def high_flow_bypass_active(self) -> bool:
        """Return whether the High Flow bypass is currently active."""
        if self.bypass_until is None:
            return False
        if self.bypass_until <= dt_util.utcnow():
            self.bypass_until = None
            self._schedule_save()
            return False
        return True

    @property
    def bypass_remaining_seconds(self) -> int:
        """Return remaining bypass duration in seconds."""
        if not self.high_flow_bypass_active or self.bypass_until is None:
            return 0
        return max(0, int((self.bypass_until - dt_util.utcnow()).total_seconds()))

    @property
    def bypass_default_minutes(self) -> float:
        """Return configured default bypass duration."""
        return float(
            self.entry.options.get(CONF_BYPASS_DEFAULT_MIN, DEFAULT_BYPASS_DEFAULT_MIN)
        )

    async def async_start_bypass(self, duration_minutes: float | None = None) -> None:
        """Start or restart the High Flow bypass."""
        minutes = (
            self.bypass_default_minutes if duration_minutes is None else duration_minutes
        )
        minutes = max(1.0, min(float(minutes), 24.0 * 60.0))
        self.bypass_until = dt_util.utcnow() + timedelta(minutes=minutes)
        await self.async_refresh()
        await self._store.async_save(self._serialize())

    async def async_cancel_bypass(self) -> None:
        """Cancel the High Flow bypass."""
        self.bypass_until = None
        await self.async_refresh()
        await self._store.async_save(self._serialize())

    async def async_set_detector_enabled(self, detector: str, enabled: bool) -> None:
        """Enable or disable one user-switchable detector."""
        key = {
            "slow": CONF_SLOW_ENABLED,
            "low": CONF_LOW_ENABLED,
        }.get(detector)
        if key is None:
            raise ValueError(f"Unsupported detector toggle: {detector}")

        options = dict(self.entry.options)
        options[key] = bool(enabled)
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self.apply_options()
        await self.async_refresh()

    async def async_set_bypass_default_minutes(self, minutes: float) -> None:
        """Update the default bypass duration from the Number entity."""
        options = dict(self.entry.options)
        options[CONF_BYPASS_DEFAULT_MIN] = max(1.0, min(float(minutes), 1440.0))
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self.apply_options()
        self._notify_listeners()

    @callback
    def apply_options(self) -> None:
        """Apply config entry options without destroying runtime state."""
        self.engine.update_settings(self._settings_from_options())
        self.notifications.reload_recipients()
        self._handle_shutoff_transition()
        self._schedule_save()
        self._notify_listeners()

    def _settings_from_options(self) -> DetectorSettings:
        opt = self.entry.options
        return DetectorSettings(
            slow_enabled=bool(opt.get(CONF_SLOW_ENABLED, DEFAULT_SLOW_ENABLED)),
            slow_threshold_lph=float(
                opt.get(CONF_SLOW_THRESHOLD_LPH, DEFAULT_SLOW_THRESHOLD_LPH)
            ),
            slow_detection_seconds=float(
                opt.get(CONF_SLOW_DETECTION_MIN, DEFAULT_SLOW_DETECTION_MIN)
            )
            * 60,
            slow_reset_seconds=float(
                opt.get(CONF_SLOW_RESET_MIN, DEFAULT_SLOW_RESET_MIN)
            )
            * 60,
            low_enabled=bool(opt.get(CONF_LOW_ENABLED, DEFAULT_LOW_ENABLED)),
            low_threshold_lph=float(
                opt.get(CONF_LOW_THRESHOLD_LPH, DEFAULT_LOW_THRESHOLD_LPH)
            ),
            low_detection_seconds=float(
                opt.get(CONF_LOW_DETECTION_MIN, DEFAULT_LOW_DETECTION_MIN)
            )
            * 60,
            low_quiet_lph=float(
                opt.get(CONF_LOW_QUIET_LPH, DEFAULT_LOW_QUIET_LPH)
            ),
            low_reset_seconds=float(
                opt.get(CONF_LOW_RESET_MIN, DEFAULT_LOW_RESET_MIN)
            )
            * 60,
            high_threshold_lph=float(
                opt.get(CONF_HIGH_THRESHOLD_LPH, DEFAULT_HIGH_THRESHOLD_LPH)
            ),
            high_detection_seconds=float(
                opt.get(CONF_HIGH_DETECTION_MIN, DEFAULT_HIGH_DETECTION_MIN)
            )
            * 60,
            high_volume_l=float(opt.get(CONF_HIGH_VOLUME_L, DEFAULT_HIGH_VOLUME_L)),
            high_quiet_lph=float(
                opt.get(CONF_HIGH_QUIET_LPH, DEFAULT_HIGH_QUIET_LPH)
            ),
            high_reset_seconds=float(
                opt.get(CONF_HIGH_RESET_MIN, DEFAULT_HIGH_RESET_MIN)
            )
            * 60,
            burst_threshold_lph=float(
                opt.get(CONF_BURST_THRESHOLD_LPH, DEFAULT_BURST_THRESHOLD_LPH)
            ),
            burst_detection_seconds=float(
                opt.get(CONF_BURST_DETECTION_SEC, DEFAULT_BURST_DETECTION_SEC)
            ),
            burst_reset_lph=float(
                opt.get(CONF_BURST_RESET_LPH, DEFAULT_BURST_RESET_LPH)
            ),
            burst_reset_seconds=float(
                opt.get(CONF_BURST_RESET_SEC, DEFAULT_BURST_RESET_SEC)
            ),
            shutoff_slow=bool(
                opt.get(CONF_SHUTOFF_SLOW, DEFAULT_SHUTOFF_SLOW)
            ),
            shutoff_low=bool(opt.get(CONF_SHUTOFF_LOW, DEFAULT_SHUTOFF_LOW)),
            shutoff_high=bool(
                opt.get(CONF_SHUTOFF_HIGH, DEFAULT_SHUTOFF_HIGH)
            ),
            shutoff_burst=bool(
                opt.get(CONF_SHUTOFF_BURST, DEFAULT_SHUTOFF_BURST)
            ),
        )

    def _handle_transitions(self, transitions: list[DetectorTransition]) -> None:
        for transition in transitions:
            if transition.new_phase is DetectorPhase.ACTIVE:
                self.hass.bus.async_fire(
                    EVENT_LEAK_STARTED,
                    self._event_payload(transition),
                )
            elif transition.old_phase is DetectorPhase.ACTIVE:
                self.hass.bus.async_fire(
                    EVENT_LEAK_ENDED,
                    self._event_payload(transition),
                )

    def _handle_shutoff_transition(self) -> None:
        current = self.engine.snapshot(self.current_total_l).shutoff_request
        if current == self._last_shutoff_request:
            return
        self._last_shutoff_request = current
        self.hass.bus.async_fire(
            EVENT_SHUTOFF_REQUESTED if current else EVENT_SHUTOFF_CLEARED,
            {
                "config_entry_id": self.entry.entry_id,
                "status": self.engine.snapshot(self.current_total_l).status,
                "flow_lph": self.current_flow_lph,
            },
        )

    def _event_payload(self, transition: DetectorTransition) -> dict[str, Any]:
        return {
            "config_entry_id": self.entry.entry_id,
            "type": transition.kind.value,
            "event_id": transition.event_id,
            "phase": transition.new_phase.value,
            "flow_lph": self.current_flow_lph,
            "volume_l": round(transition.volume_l, 3),
            "started_at": transition.started_at.isoformat()
            if transition.started_at
            else None,
            "detected_at": transition.detected_at.isoformat()
            if transition.detected_at
            else None,
        }

    def _serialize(self) -> dict[str, Any]:
        return {
            "engine": self.engine.to_dict(),
            "bypass_until": self.bypass_until.isoformat()
            if self.bypass_until
            else None,
            "acknowledgements": self.notifications.to_dict(),
        }

    @callback
    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._serialize, delay=10)
