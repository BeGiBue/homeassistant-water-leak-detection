"""Tests for notification recipient and acknowledgement primitives."""

from datetime import UTC, datetime

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
