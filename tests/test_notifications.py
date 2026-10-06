"""Tests for notification recipient and acknowledgement primitives."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.water_leak_detection.const import (
    ACTION_ACK_ALL,
    ACTION_MUTE,
    RECIPIENT_ALLOW_GLOBAL_ACK,
    RECIPIENT_CRITICAL_ENABLED,
    RECIPIENT_ID,
    RECIPIENT_NAME,
    RECIPIENT_NOTIFY_SERVICE,
    RECIPIENT_TOKEN,
    RECIPIENT_TRACKER_ENTITY,
    RECIPIENT_TRUSTED_STATIONARY,
)
from custom_components.water_leak_detection.notifications import (
    EventAcknowledgement,
    NotificationController,
    NotificationRecipient,
)


def _recipient_raw() -> dict[str, object]:
    return {
        RECIPIENT_ID: "ipad_home",
        RECIPIENT_NAME: "Home iPad",
        RECIPIENT_NOTIFY_SERVICE: "notify.mobile_app_ipad",
        RECIPIENT_TRACKER_ENTITY: "device_tracker.ipad",
        RECIPIENT_CRITICAL_ENABLED: True,
        RECIPIENT_ALLOW_GLOBAL_ACK: True,
        RECIPIENT_TRUSTED_STATIONARY: True,
        RECIPIENT_TOKEN: "secret-token",
    }


def test_recipient_parses_stationary_home_device() -> None:
    recipient = NotificationRecipient.from_dict(_recipient_raw())

    assert recipient is not None
    assert recipient.id == "ipad_home"
    assert recipient.notify_service == "notify.mobile_app_ipad"
    assert recipient.tracker_entity == "device_tracker.ipad"
    assert recipient.allow_global_ack is True
    assert recipient.trusted_stationary is True


def test_invalid_recipient_service_is_rejected() -> None:
    raw = _recipient_raw()
    raw[RECIPIENT_NOTIFY_SERVICE] = "persistent_notification.create"

    assert NotificationRecipient.from_dict(raw) is None


def test_event_acknowledgement_round_trip() -> None:
    acknowledged_at = datetime(2026, 10, 6, 8, 30, tzinfo=UTC)
    original = EventAcknowledgement(
        globally_acknowledged=True,
        globally_acknowledged_by="ipad_home",
        globally_acknowledged_at=acknowledged_at,
        muted_recipients={"iphone_benedikt"},
    )

    restored = EventAcknowledgement.from_dict(original.to_dict())

    assert restored.globally_acknowledged is True
    assert restored.globally_acknowledged_by == "ipad_home"
    assert restored.globally_acknowledged_at == acknowledged_at
    assert restored.muted_recipients == {"iphone_benedikt"}


def test_action_parser_accepts_mute_and_global_ack() -> None:
    mute = "WLD|MUTE|entry123|slow_leak_1|iphone|token"
    global_ack = "WLD|ACK_ALL|entry123|slow_leak_1|ipad|token2"

    assert NotificationController._parse_action(mute) == (
        ACTION_MUTE,
        "entry123",
        "slow_leak_1",
        "iphone",
        "token",
    )
    assert NotificationController._parse_action(global_ack) == (
        ACTION_ACK_ALL,
        "entry123",
        "slow_leak_1",
        "ipad",
        "token2",
    )


def test_action_parser_rejects_unknown_action() -> None:
    assert (
        NotificationController._parse_action(
            "WLD|DELETE|entry123|slow_leak_1|iphone|token"
        )
        is None
    )


class _FakeBus:
    def __init__(self) -> None:
        self.fired: list[tuple[str, dict[str, object]]] = []

    def async_fire(self, event_type: str, data: dict[str, object]) -> None:
        self.fired.append((event_type, data))


class _FakeStates:
    def __init__(self, states: dict[str, str]) -> None:
        self._states = states

    def get(self, entity_id: str):
        value = self._states.get(entity_id)
        return SimpleNamespace(state=value) if value is not None else None


class _FakeHass:
    def __init__(self, states: dict[str, str]) -> None:
        self.bus = _FakeBus()
        self.states = _FakeStates(states)


def _controller_for_action(*, tracker_state: str):
    hass = _FakeHass({"device_tracker.ipad": tracker_state})
    snapshot = SimpleNamespace(
        active_event_id="slow_leak_1",
        active_kind=SimpleNamespace(value="slow_leak"),
        active_volume_l=12.0,
        active_started_at=datetime(2026, 10, 6, 7, 0, tzinfo=UTC),
    )
    manager = SimpleNamespace(
        current_total_l=None,
        current_flow_lph=7.0,
        engine=SimpleNamespace(snapshot=lambda _total: snapshot),
    )
    entry = SimpleNamespace(entry_id="entry123", options={})
    persisted: list[bool] = []
    controller = NotificationController(
        hass,
        entry,
        manager,
        lambda: persisted.append(True),
    )
    recipient = NotificationRecipient.from_dict(_recipient_raw())
    assert recipient is not None
    controller.recipients = {recipient.id: recipient}
    return controller, recipient, hass, persisted


@pytest.mark.asyncio
async def test_remote_device_can_mute_only_itself() -> None:
    controller, recipient, _hass, persisted = _controller_for_action(
        tracker_state="not_home"
    )
    event = SimpleNamespace(
        data={
            "action": (
                "WLD|MUTE|entry123|slow_leak_1|"
                f"{recipient.id}|{recipient.token}"
            )
        }
    )

    await controller._async_mobile_action(event)

    state = controller.acknowledgements["slow_leak_1"]
    assert recipient.id in state.muted_recipients
    assert state.globally_acknowledged is False
    assert persisted


@pytest.mark.asyncio
async def test_remote_device_cannot_acknowledge_globally() -> None:
    controller, recipient, hass, persisted = _controller_for_action(
        tracker_state="not_home"
    )
    controller._async_send_feedback = AsyncMock()
    event = SimpleNamespace(
        data={
            "action": (
                "WLD|ACK_ALL|entry123|slow_leak_1|"
                f"{recipient.id}|{recipient.token}"
            )
        }
    )

    await controller._async_mobile_action(event)

    state = controller.acknowledgements["slow_leak_1"]
    assert state.globally_acknowledged is False
    assert not persisted
    assert any(
        data.get("reason") == "device_not_home"
        for _event_type, data in hass.bus.fired
    )


@pytest.mark.asyncio
async def test_home_device_can_acknowledge_globally() -> None:
    controller, recipient, _hass, persisted = _controller_for_action(
        tracker_state="home"
    )
    event = SimpleNamespace(
        data={
            "action": (
                "WLD|ACK_ALL|entry123|slow_leak_1|"
                f"{recipient.id}|{recipient.token}"
            )
        }
    )

    await controller._async_mobile_action(event)

    state = controller.acknowledgements["slow_leak_1"]
    assert state.globally_acknowledged is True
    assert state.globally_acknowledged_by == recipient.id
    assert state.globally_acknowledged_at is not None
    assert persisted


@pytest.mark.asyncio
async def test_arriving_home_retriggers_unacknowledged_alarm() -> None:
    controller, recipient, _hass, persisted = _controller_for_action(
        tracker_state="home"
    )
    controller.acknowledgements["slow_leak_1"] = EventAcknowledgement(
        muted_recipients={recipient.id}
    )
    controller._async_send_event_notification = AsyncMock()
    event = SimpleNamespace(
        data={
            "entity_id": recipient.tracker_entity,
            "old_state": SimpleNamespace(state="not_home"),
            "new_state": SimpleNamespace(state="home"),
        }
    )

    await controller._async_tracker_changed(event)

    assert (
        recipient.id
        not in controller.acknowledgements["slow_leak_1"].muted_recipients
    )
    controller._async_send_event_notification.assert_awaited_once()
    assert persisted


@pytest.mark.asyncio
async def test_arriving_home_does_not_retrigger_globally_acknowledged_event() -> None:
    controller, recipient, _hass, _persisted = _controller_for_action(
        tracker_state="home"
    )
    controller.acknowledgements["slow_leak_1"] = EventAcknowledgement(
        globally_acknowledged=True
    )
    controller._async_send_event_notification = AsyncMock()
    event = SimpleNamespace(
        data={
            "entity_id": recipient.tracker_entity,
            "old_state": SimpleNamespace(state="not_home"),
            "new_state": SimpleNamespace(state="home"),
        }
    )

    await controller._async_tracker_changed(event)

    controller._async_send_event_notification.assert_not_awaited()
