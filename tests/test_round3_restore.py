"""Class-independent redundant confirmation and action-safe restored event IDs."""

import pytest
from test_manager_runtime import report
from test_round2_measurements import measurement_origin

from custom_components.water_leak_detection.const import DOMAIN, DetectorKind, DetectorPhase
from custom_components.water_leak_detection.engine import DetectionEngine, DetectorSettings
from custom_components.water_leak_detection.manager import WaterLeakManager
from custom_components.water_leak_detection.notifications import NotificationController


@pytest.mark.parametrize("kind", list(DetectorKind))
@pytest.mark.parametrize(
    "fields",
    [
        {"phase": "bad"},
        {"event_id": None},
        {"phase": "bad", "event_id": None},
        {"phase": "idle", "event_id": "broken|id", "reason": None},
        {"detected_at": "bad"},
        {"reason": None},
        {"estimated_volume_l": "bad"},
        {"phase": [], "event_id": "broken|id", "reason": None},
        {"phase": "bad", "event_id": None, "detected_at": None, "estimated_volume_l": None},
    ],
)
@pytest.mark.parametrize("legacy", [True, False])
def test_f16_all_classes_restore_confirmed_events_without_burst_reason(kind, fields, legacy):
    engine = DetectionEngine(
        DetectorSettings(shutoff_slow=True, shutoff_low=True, shutoff_high=True, shutoff_burst=True)
    )
    runtime = engine.runtimes[kind]
    runtime.phase = DetectorPhase.ACTIVE
    runtime.event_id = f"{kind.value}_confirmed"
    runtime.started_at = runtime.detected_at = measurement_origin()
    runtime.estimated_volume_l = 0  # Confirmation never depends on a positive volume.
    raw = engine.to_dict()
    if legacy:
        raw["runtimes"][kind.value].pop("confirmed_active")
    raw["runtimes"][kind.value].update(fields)
    restored = DetectionEngine(engine.settings)
    restored.restore(raw)
    # A legacy store with all confirmation signals lost cannot be reconstructed.
    if (
        legacy
        and fields.get("detected_at", "present") is None
        and fields.get("event_id", "present") is None
    ):
        assert not restored.snapshot().alarm_active
        assert not restored.snapshot().shutoff_request
        return
    assert restored.runtimes[kind].phase is DetectorPhase.ACTIVE
    assert restored.snapshot().shutoff_request
    assert restored.runtimes[kind].event_id
    assert restored.runtimes[kind].quiet_since is None


@pytest.mark.parametrize("kind", list(DetectorKind))
@pytest.mark.parametrize(
    "raw",
    [
        {},
        {"phase": "bad"},
        {
            "phase": "monitoring",
            "event_id": None,
            "started_at": measurement_origin().isoformat(),
            "reason": "optional",
            "estimated_volume_l": 20,
        },
        {
            "phase": "bad",
            "event_id": None,
            "started_at": measurement_origin().isoformat(),
            "estimated_volume_l": 20,
            "confirmed_active": False,
        },
    ],
)
def test_f16_unconfirmed_monitoring_never_creates_safety_state(kind, raw):
    engine = DetectionEngine()
    engine.restore({"runtimes": {kind.value: raw}})
    assert not engine.snapshot().alarm_active
    assert not engine.snapshot().shutoff_request


@pytest.mark.parametrize("event_id", ["broken|id", "", " ", "a" * 129, "äö", "id\n", [], None])
async def test_f16_invalid_id_is_replaced_without_old_ack_and_actions_parse(
    runtime_hass, runtime_entry, measurement_clock, event_id
):
    now = measurement_clock.utcnow().isoformat()
    manager = WaterLeakManager(runtime_hass, runtime_entry)
    await manager._store.async_save(
        {
            "engine": {
                "runtimes": {
                    "burst_leak": {
                        "phase": "active",
                        "event_id": event_id,
                        "detected_at": now,
                        "started_at": now,
                    }
                }
            },
            "acknowledgements": {str(event_id): {"globally_acknowledged": True}},
        }
    )
    report(runtime_hass, measurement_clock, "unavailable")
    runtime_hass.data.setdefault(DOMAIN, {})[runtime_entry.entry_id] = manager
    await manager.async_setup()
    new_id = manager.engine.snapshot().active_event_id
    assert new_id and new_id != event_id
    assert manager.engine.snapshot().shutoff_request
    assert not manager.notifications.acknowledgements[new_id].globally_acknowledged
    from test_notification_runtime import recipient

    from custom_components.water_leak_detection.notifications import NotificationRecipient

    phone = NotificationRecipient.from_dict(recipient("phone"))
    action = manager.notifications._action_id("ACK_ALL", new_id, phone)
    assert NotificationController._parse_action(action)[2] == new_id


@pytest.mark.parametrize("event_id", ["burst_leak_confirmed", "OLD-event_123", "a" * 128])
def test_f16_valid_existing_ids_preserved(event_id):
    engine = DetectionEngine()
    engine.restore({"runtimes": {"burst_leak": {"phase": "active", "event_id": event_id}}})
    assert engine.snapshot().active_event_id == event_id


@pytest.mark.parametrize("kind", list(DetectorKind))
@pytest.mark.parametrize(
    "damage",
    [
        {"phase": "bad"},
        {"event_id": None},
        {"phase": "idle", "event_id": None},
        {"detected_at": []},
        {"reason": []},
        {"estimated_volume_l": "nan"},
        {"phase": None, "event_id": "broken|id", "detected_at": None, "reason": None},
    ],
)
async def test_f16_real_store_setup_retains_every_class_and_shutoff(
    runtime_hass, runtime_entry, measurement_clock, kind, damage
):
    runtime_hass.config_entries.async_update_entry(
        runtime_entry,
        options={
            "shutoff_slow": True,
            "shutoff_low": True,
            "shutoff_high": True,
            "shutoff_burst": True,
        },
    )
    manager = WaterLeakManager(runtime_hass, runtime_entry)
    runtime = manager.engine.runtimes[kind]
    runtime.phase = DetectorPhase.ACTIVE
    runtime.event_id = f"{kind.value}_stored"
    runtime.started_at = runtime.detected_at = measurement_clock.utcnow()
    raw = manager._serialize()
    raw["engine"]["runtimes"][kind.value].update(damage)
    await manager._store.async_save(raw)
    report(runtime_hass, measurement_clock, "unavailable")
    restored = WaterLeakManager(runtime_hass, runtime_entry)
    runtime_hass.data.setdefault(DOMAIN, {})[runtime_entry.entry_id] = restored
    await restored.async_setup()
    assert restored.engine.runtimes[kind].phase is DetectorPhase.ACTIVE
    assert restored.engine.snapshot().shutoff_request
    assert restored.engine.runtimes[kind].event_id
