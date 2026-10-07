"""Isolated HA service handoffs, never physical mobile-delivery claims."""

import asyncio

from homeassistant.core import Event
from test_manager_runtime import report, start_manager
from test_notification_runtime import activate, configure

from custom_components.water_leak_detection.const import DOMAIN, MOBILE_ACTION_EVENT
from custom_components.water_leak_detection.manager import WaterLeakManager
from custom_components.water_leak_detection.notifications import DispatchState, EventAcknowledgement


async def test_f06_slow_service_over_five_seconds_is_not_timed_out_or_redispatched(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "slow", "fast")
    calls, entered, done, fast_done = [], asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def slow(call):
        calls.append("slow")
        entered.set()
        await asyncio.sleep(5.1)
        done.set()
    async def fast(call):
        calls.append("fast")
        fast_done.set()
    runtime_hass.services.async_register("notify", "mobile_app_slow", slow)
    runtime_hass.services.async_register("notify", "mobile_app_fast", fast)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    event_id = await activate(manager, runtime_hass, measurement_clock, drain=False)
    await asyncio.wait_for(entered.wait(), 1)
    await asyncio.wait_for(fast_done.wait(), 1)
    state = manager.notifications.acknowledgements[event_id]
    assert state.dispatch_states["slow"] == DispatchState.IN_FLIGHT
    for _ in range(10):
        await manager.notifications.async_retry_pending()
    assert calls.count("slow") == 1
    await asyncio.wait_for(done.wait(), 7)
    await runtime_hass.async_block_till_done()
    assert state.dispatch_states["slow"] == DispatchState.ACCEPTED
    assert "slow" in state.accepted_recipients
    await manager.notifications.async_retry_pending()
    assert calls.count("slow") == calls.count("fast") == 1


async def test_f06_hanging_recipient_does_not_block_others_and_unload_records_ambiguity(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "hang", "good")
    entered, release, good_done = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = []
    async def hanging(call):
        calls.append("hang")
        entered.set()
        await release.wait()
    async def good(call):
        calls.append("good")
        good_done.set()
    runtime_hass.services.async_register("notify", "mobile_app_hang", hanging)
    runtime_hass.services.async_register("notify", "mobile_app_good", good)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    event_id = await activate(manager, runtime_hass, measurement_clock, drain=False)
    await asyncio.wait_for(entered.wait(), 1)
    await asyncio.wait_for(good_done.wait(), 1)
    for _ in range(20):
        await manager._async_tick(measurement_clock.utcnow())
    assert calls.count("hang") == calls.count("good") == 1
    await asyncio.wait_for(manager.async_unload(), 1)
    assert not manager.notifications._dispatch_tasks
    assert not manager.notifications._delivery_tasks
    state = manager.notifications.acknowledgements[event_id]
    assert state.dispatch_states["hang"] == DispatchState.INTERRUPTED
    release.set()
    await runtime_hass.async_block_till_done()
    report(runtime_hass, measurement_clock, 2500)
    restored = WaterLeakManager(runtime_hass, runtime_entry)
    runtime_hass.data[DOMAIN][runtime_entry.entry_id] = restored
    await restored.async_setup()
    assert calls.count("hang") == calls.count("good") == 1
    assert restored.engine.snapshot().shutoff_request


async def test_f06_ack_during_handoff_stops_only_not_yet_started_dispatches(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "slow", "queued")
    entered, release = asyncio.Event(), asyncio.Event()
    translation_entered, translation_release = asyncio.Event(), asyncio.Event()
    calls = []
    async def slow(call):
        calls.append("slow")
        entered.set()
        await release.wait()
    async def queued(call):
        calls.append("queued")
    runtime_hass.services.async_register("notify", "mobile_app_slow", slow)
    runtime_hass.services.async_register("notify", "mobile_app_queued", queued)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    translations = [0]
    async def translate():
        translations[0] += 1
        if translations[0] == 2:
            translation_entered.set()
            await translation_release.wait()
        return {}
    manager.notifications._async_common_translations = translate
    event_id = await activate(manager, runtime_hass, measurement_clock, drain=False)
    await asyncio.wait_for(entered.wait(), 1)
    await asyncio.wait_for(translation_entered.wait(), 1)
    phone = manager.notifications.recipients["slow"]
    action = manager.notifications._action_id("ACK_ALL", event_id, phone)
    await manager.notifications._async_mobile_action(Event(MOBILE_ACTION_EVENT, {"action": action}))
    assert manager.engine.snapshot().active_event_id == event_id
    assert manager.engine.snapshot().shutoff_request
    translation_release.set()
    release.set()
    await runtime_hass.async_block_till_done()
    assert calls == ["slow"]
    state = manager.notifications.acknowledgements[event_id]
    assert state.dispatch_states["slow"] == DispatchState.ACCEPTED
    assert state.dispatch_states["queued"] == DispatchState.NOT_DISPATCHED


def test_f06_dispatch_state_restore_migration_and_corrupt_fields():
    old = EventAcknowledgement.from_dict({"delivered_recipients": {"phone": "old-key"}})
    assert old.accepted_recipients == {"phone": "old-key"}
    assert "delivered_recipients" not in old.to_dict()
    pending = EventAcknowledgement.from_dict({"dispatch_states": {
        "phone": "in_flight", "broken": [], "unknown": "bogus",
    }})
    assert pending.dispatch_states == {"phone": "interrupted"}


async def test_f06_event_ends_before_worker_first_turn_leaves_no_orphan_task(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    event_id = await activate(manager, runtime_hass, measurement_clock)
    controller = manager.notifications
    calls = []
    async def service(call):
        calls.append(call.data)
    runtime_hass.services.async_register("notify", "mobile_app_phone", service)
    async def ended():
        from custom_components.water_leak_detection.const import DetectorKind
        manager.engine.runtimes[DetectorKind.BURST_LEAK].reset()
        await controller._async_leak_ended(Event("ended", {
            "event_id": event_id, "config_entry_id": runtime_entry.entry_id,
        }))
    retry = asyncio.create_task(controller.async_retry_pending())
    ending = asyncio.create_task(ended())
    await asyncio.gather(retry, ending)
    await asyncio.sleep(0)
    assert not controller._dispatch_tasks
    assert not controller._delivery_tasks
    assert calls == []


async def test_f06_service_return_only_records_ha_acceptance_not_remote_receipt(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    calls = []
    async def service(call):
        calls.append(call.data)
        try:
            raise RuntimeError("simulated push failure handled inside mobile_app")
        except RuntimeError:
            return  # The integration cannot observe this internally handled failure.
    runtime_hass.services.async_register("notify", "mobile_app_phone", service)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    event_id = await activate(manager, runtime_hass, measurement_clock)
    state = manager.notifications.acknowledgements[event_id]
    assert state.dispatch_states["phone"] == DispatchState.ACCEPTED
    await manager.notifications.async_retry_pending()
    assert len(calls) == 1
    assert "accepted_recipients" in state.to_dict()
