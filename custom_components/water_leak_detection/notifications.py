"""Companion notification and acknowledgement handling."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    ACTION_ACK_ALL,
    ACTION_MUTE,
    ACTION_PREFIX,
    CONF_NOTIFICATION_RECIPIENTS,
    EVENT_ACKNOWLEDGED,
    EVENT_ACK_REJECTED,
    EVENT_LEAK_ENDED,
    EVENT_LEAK_STARTED,
    MOBILE_ACTION_EVENT,
    RECIPIENT_ALLOW_GLOBAL_ACK,
    RECIPIENT_CRITICAL_ENABLED,
    RECIPIENT_ID,
    RECIPIENT_NAME,
    RECIPIENT_NOTIFY_SERVICE,
    RECIPIENT_TOKEN,
    RECIPIENT_TRACKER_ENTITY,
    RECIPIENT_TRUSTED_STATIONARY,
    DetectorKind,
)

if TYPE_CHECKING:
    from .manager import WaterLeakManager

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class NotificationRecipient:
    """One configured Companion notification target."""

    id: str
    name: str
    notify_service: str
    tracker_entity: str
    critical_enabled: bool
    allow_global_ack: bool
    trusted_stationary: bool
    token: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "NotificationRecipient | None":
        """Create a recipient from config-entry options."""
        try:
            recipient_id = str(raw[RECIPIENT_ID])
            name = str(raw[RECIPIENT_NAME])
            notify_service = str(raw[RECIPIENT_NOTIFY_SERVICE])
            tracker_entity = str(raw[RECIPIENT_TRACKER_ENTITY])
            token = str(raw[RECIPIENT_TOKEN])
        except (KeyError, TypeError, ValueError):
            return None

        if (
            not recipient_id
            or not name
            or not notify_service.startswith("notify.")
            or not tracker_entity.startswith("device_tracker.")
            or not token
        ):
            return None

        return cls(
            id=recipient_id,
            name=name,
            notify_service=notify_service,
            tracker_entity=tracker_entity,
            critical_enabled=bool(raw.get(RECIPIENT_CRITICAL_ENABLED, True)),
            allow_global_ack=bool(raw.get(RECIPIENT_ALLOW_GLOBAL_ACK, True)),
            trusted_stationary=bool(raw.get(RECIPIENT_TRUSTED_STATIONARY, False)),
            token=token,
        )


@dataclass(slots=True)
class EventAcknowledgement:
    """Acknowledgement state belonging to one leak event ID."""

    globally_acknowledged: bool = False
    globally_acknowledged_by: str | None = None
    globally_acknowledged_at: datetime | None = None
    muted_recipients: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        """Serialize acknowledgement state."""
        return {
            "globally_acknowledged": self.globally_acknowledged,
            "globally_acknowledged_by": self.globally_acknowledged_by,
            "globally_acknowledged_at": (
                self.globally_acknowledged_at.isoformat()
                if self.globally_acknowledged_at
                else None
            ),
            "muted_recipients": sorted(self.muted_recipients),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EventAcknowledgement":
        """Restore acknowledgement state."""
        acknowledged_at = raw.get("globally_acknowledged_at")
        parsed_at = (
            dt_util.parse_datetime(acknowledged_at)
            if isinstance(acknowledged_at, str)
            else None
        )
        muted = raw.get("muted_recipients", [])
        return cls(
            globally_acknowledged=bool(raw.get("globally_acknowledged", False)),
            globally_acknowledged_by=(
                str(raw["globally_acknowledged_by"])
                if raw.get("globally_acknowledged_by")
                else None
            ),
            globally_acknowledged_at=parsed_at,
            muted_recipients={
                str(item) for item in muted if isinstance(item, (str, int))
            },
        )


class NotificationController:
    """Send notifications and enforce acknowledgement authorization."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        manager: WaterLeakManager,
        persist_callback: Callable[[], None],
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.manager = manager
        self._persist_callback = persist_callback
        self.recipients: dict[str, NotificationRecipient] = {}
        self.acknowledgements: dict[str, EventAcknowledgement] = {}
        self._unsubs: list[Callable[[], None]] = []
        self._tracker_unsub: Callable[[], None] | None = None

    async def async_setup(self) -> None:
        """Register event and presence listeners."""
        self._unsubs.append(
            self.hass.bus.async_listen(MOBILE_ACTION_EVENT, self._async_mobile_action)
        )
        self._unsubs.append(
            self.hass.bus.async_listen(EVENT_LEAK_STARTED, self._async_leak_started)
        )
        self._unsubs.append(
            self.hass.bus.async_listen(EVENT_LEAK_ENDED, self._async_leak_ended)
        )
        self.reload_recipients()

    async def async_unload(self) -> None:
        """Remove listeners."""
        if self._tracker_unsub is not None:
            self._tracker_unsub()
            self._tracker_unsub = None
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def reload_recipients(self) -> None:
        """Reload recipient configuration after Options Flow changes."""
        raw_recipients = self.entry.options.get(CONF_NOTIFICATION_RECIPIENTS, [])
        recipients: dict[str, NotificationRecipient] = {}
        if isinstance(raw_recipients, list):
            for raw in raw_recipients:
                if not isinstance(raw, dict):
                    continue
                recipient = NotificationRecipient.from_dict(raw)
                if recipient is not None:
                    recipients[recipient.id] = recipient
        self.recipients = recipients

        if self._tracker_unsub is not None:
            self._tracker_unsub()
            self._tracker_unsub = None

        trackers = sorted({r.tracker_entity for r in recipients.values()})
        if trackers:
            self._tracker_unsub = async_track_state_change_event(
                self.hass,
                trackers,
                self._async_tracker_changed,
            )

    def restore(self, raw: Any) -> None:
        """Restore acknowledgement state from persistent storage."""
        if not isinstance(raw, dict):
            return
        restored: dict[str, EventAcknowledgement] = {}
        for event_id, state in raw.items():
            if isinstance(event_id, str) and isinstance(state, dict):
                restored[event_id] = EventAcknowledgement.from_dict(state)
        self.acknowledgements = restored

    def to_dict(self) -> dict[str, Any]:
        """Serialize acknowledgement state."""
        return {
            event_id: state.to_dict()
            for event_id, state in self.acknowledgements.items()
        }

    def state_for(self, event_id: str | None) -> EventAcknowledgement | None:
        """Return acknowledgement state for an event."""
        if event_id is None:
            return None
        return self.acknowledgements.get(event_id)

    async def _async_leak_started(self, event: Event) -> None:
        if event.data.get("config_entry_id") != self.entry.entry_id:
            return
        event_id = event.data.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            return

        state = self.acknowledgements.setdefault(event_id, EventAcknowledgement())
        self._persist_callback()
        if state.globally_acknowledged:
            return

        detector_type = str(event.data.get("type", "unknown"))
        for recipient in self.recipients.values():
            if recipient.id in state.muted_recipients:
                continue
            await self._async_send_event_notification(
                recipient,
                event_id,
                detector_type,
                event.data,
                returning_home=False,
            )

    async def _async_leak_ended(self, event: Event) -> None:
        if event.data.get("config_entry_id") != self.entry.entry_id:
            return
        event_id = event.data.get("event_id")
        if isinstance(event_id, str):
            self.acknowledgements.pop(event_id, None)
            self._persist_callback()

    async def _async_mobile_action(self, event: Event) -> None:
        action = event.data.get("action")
        if not isinstance(action, str) or not action.startswith(f"{ACTION_PREFIX}|"):
            return

        parsed = self._parse_action(action)
        if parsed is None:
            return
        action_kind, entry_id, event_id, recipient_id, token = parsed
        if entry_id != self.entry.entry_id:
            return

        recipient = self.recipients.get(recipient_id)
        if recipient is None or recipient.token != token:
            self._fire_rejected(event_id, recipient_id, "invalid_recipient_or_token")
            return

        snapshot = self.manager.engine.snapshot(self.manager.current_total_l)
        if snapshot.active_event_id != event_id:
            self._fire_rejected(event_id, recipient_id, "event_not_active")
            return

        state = self.acknowledgements.setdefault(event_id, EventAcknowledgement())

        if action_kind == ACTION_MUTE:
            state.muted_recipients.add(recipient_id)
            self._persist_callback()
            self.hass.bus.async_fire(
                EVENT_ACKNOWLEDGED,
                {
                    "config_entry_id": self.entry.entry_id,
                    "event_id": event_id,
                    "recipient_id": recipient_id,
                    "scope": "device",
                },
            )
            return

        if action_kind != ACTION_ACK_ALL:
            return

        if not recipient.allow_global_ack:
            self._fire_rejected(event_id, recipient_id, "global_ack_not_allowed")
            return

        tracker = self.hass.states.get(recipient.tracker_entity)
        if tracker is None or tracker.state != "home":
            self._fire_rejected(event_id, recipient_id, "device_not_home")
            await self._async_send_feedback(
                recipient,
                "Global acknowledgement rejected",
                "This device is not currently in the Home zone. The alarm can only be muted for this device.",
            )
            return

        state.globally_acknowledged = True
        state.globally_acknowledged_by = recipient_id
        state.globally_acknowledged_at = dt_util.utcnow()
        self._persist_callback()
        self.hass.bus.async_fire(
            EVENT_ACKNOWLEDGED,
            {
                "config_entry_id": self.entry.entry_id,
                "event_id": event_id,
                "recipient_id": recipient_id,
                "scope": "global",
                "trusted_stationary": recipient.trusted_stationary,
            },
        )

    async def _async_tracker_changed(self, event: Event) -> None:
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if old_state is None or new_state is None:
            return
        if old_state.state == "home" or new_state.state != "home":
            return

        tracker_entity = event.data.get("entity_id")
        if not isinstance(tracker_entity, str):
            return

        snapshot = self.manager.engine.snapshot(self.manager.current_total_l)
        event_id = snapshot.active_event_id
        if event_id is None or snapshot.active_kind is None:
            return

        state = self.acknowledgements.get(event_id)
        if state is None or state.globally_acknowledged:
            return

        for recipient in self.recipients.values():
            if recipient.tracker_entity != tracker_entity:
                continue

            # Returning Home is a fresh safety context. Re-notify every configured
            # recipient on that device while the event remains globally unacknowledged.
            # A previous personal mute is cleared at the same time.
            state.muted_recipients.discard(recipient.id)
            self._persist_callback()
            await self._async_send_event_notification(
                recipient,
                event_id,
                snapshot.active_kind.value,
                {
                    "flow_lph": self.manager.current_flow_lph,
                    "volume_l": snapshot.active_volume_l,
                    "started_at": (
                        snapshot.active_started_at.isoformat()
                        if snapshot.active_started_at
                        else None
                    ),
                },
                returning_home=True,
            )

    async def _async_send_event_notification(
        self,
        recipient: NotificationRecipient,
        event_id: str,
        detector_type: str,
        payload: dict[str, Any],
        *,
        returning_home: bool,
    ) -> None:
        domain, service = recipient.notify_service.split(".", 1)
        if not self.hass.services.has_service(domain, service):
            _LOGGER.warning(
                "Notification service %s for recipient %s is unavailable",
                recipient.notify_service,
                recipient.name,
            )
            return

        is_burst = detector_type == DetectorKind.BURST_LEAK.value
        title = (
            "Water leak still active"
            if returning_home
            else f"Water leak detection: {detector_type.replace('_', ' ').title()}"
        )

        message_parts: list[str] = []
        if returning_home:
            message_parts.append("You returned home while this event is still active.")
        flow = payload.get("flow_lph")
        if isinstance(flow, (int, float)):
            message_parts.append(f"Current flow: {float(flow):.1f} L/h.")
        volume = payload.get("volume_l")
        if isinstance(volume, (int, float)):
            message_parts.append(f"Volume since detection started: {float(volume):.1f} L.")
        if not message_parts:
            message_parts.append("A water event is active.")

        notification_data: dict[str, Any] = {
            "tag": f"wld_{self.entry.entry_id}_{event_id}",
            "wld_event_id": event_id,
            "wld_recipient_id": recipient.id,
            "actions": [
                {
                    "action": self._action_id(
                        ACTION_MUTE, event_id, recipient
                    ),
                    "title": "Mute for this device",
                }
            ],
        }

        if recipient.allow_global_ack:
            notification_data["actions"].append(
                {
                    "action": self._action_id(
                        ACTION_ACK_ALL, event_id, recipient
                    ),
                    "title": "Acknowledge for everyone",
                }
            )

        if is_burst and recipient.critical_enabled:
            notification_data.update(
                {
                    "ttl": 0,
                    "priority": "high",
                    "channel": "alarm_stream",
                    "push": {"interruption-level": "critical"},
                }
            )

        await self.hass.services.async_call(
            domain,
            service,
            {
                "title": title,
                "message": " ".join(message_parts),
                "data": notification_data,
            },
            blocking=False,
        )

    async def _async_send_feedback(
        self,
        recipient: NotificationRecipient,
        title: str,
        message: str,
    ) -> None:
        domain, service = recipient.notify_service.split(".", 1)
        if not self.hass.services.has_service(domain, service):
            return
        await self.hass.services.async_call(
            domain,
            service,
            {"title": title, "message": message},
            blocking=False,
        )

    def _action_id(
        self,
        action_kind: str,
        event_id: str,
        recipient: NotificationRecipient,
    ) -> str:
        return "|".join(
            (
                ACTION_PREFIX,
                action_kind,
                self.entry.entry_id,
                event_id,
                recipient.id,
                recipient.token,
            )
        )

    @staticmethod
    def _parse_action(
        action: str,
    ) -> tuple[str, str, str, str, str] | None:
        parts = action.split("|")
        if len(parts) != 6 or parts[0] != ACTION_PREFIX:
            return None
        _, action_kind, entry_id, event_id, recipient_id, token = parts
        if action_kind not in (ACTION_MUTE, ACTION_ACK_ALL):
            return None
        return action_kind, entry_id, event_id, recipient_id, token

    def _fire_rejected(
        self,
        event_id: str,
        recipient_id: str,
        reason: str,
    ) -> None:
        self.hass.bus.async_fire(
            EVENT_ACK_REJECTED,
            {
                "config_entry_id": self.entry.entry_id,
                "event_id": event_id,
                "recipient_id": recipient_id,
                "reason": reason,
            },
        )
