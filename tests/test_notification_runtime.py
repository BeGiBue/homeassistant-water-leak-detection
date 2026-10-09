"""Delivery/acknowledgement regressions with real HA services and event bus."""

import asyncio
from unittest.mock import AsyncMock

from homeassistant.core import Event
from test_manager_runtime import report, start_manager

from custom_components.water_leak_detection.const import (
    CONF_NOTIFICATION_RECIPIENTS,
    CONF_SOURCE_MAX_AGE_SEC,
    DOMAIN,
    MOBILE_ACTION_EVENT,
    DetectorKind,
)
from custom_components.water_leak_detection.engine import DetectorSettings
from custom_components.water_leak_detection.manager import WaterLeakManager


def recipient(name):
    return {
        "id": name, "name": name, "notify_service": f"notify.mobile_app_{name}",
        "tracker_entity": f"device_tracker.{name}", "token": f"token_{name}",
        "critical_enabled": True, "allow_global_ack": True, "trusted_stationary": False,
    }


def configure(hass, entry, clock, *names):
    hass.config_entries.async_update_entry(entry, options={
        CONF_NOTIFICATION_RECIPIENTS: [recipient(name) for name in names],
        CONF_SOURCE_MAX_AGE_SEC: 10,  # Routing tests use an explicitly known cadence.
    })
    for name in names:
        hass.states.async_set(f"device_tracker.{name}", "home",
                              timestamp=clock.utcnow().timestamp())


async def activate(manager, hass, clock, *, drain=True):
    for _ in range(4):
        report(hass, clock, 2500)
        await manager.async_refresh()
        if drain:
            await hass.async_block_till_done()
        clock.advance(10)
    return manager.engine.runtimes[DetectorKind.BURST_LEAK].event_id


async def test_f06_unavailable_service_retries_and_restores_pending_delivery(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    event_id = await activate(manager, runtime_hass, measurement_clock)
    assert not manager.notifications.acknowledgements[event_id].delivered_recipients
    await manager.async_unload()
    calls = []
    async def notify(call):
        calls.append(call.data)
    runtime_hass.services.async_register("notify", "mobile_app_phone", notify)
    report(runtime_hass, measurement_clock, 2500)
    restored = WaterLeakManager(runtime_hass, runtime_entry)
    restored.notifications._async_common_translations = AsyncMock(return_value={})
    runtime_hass.data[DOMAIN][runtime_entry.entry_id] = restored
    await restored.async_setup()
    assert len(calls) == 1
    assert calls[0]["data"]["wld_event_id"] == event_id
    await restored.notifications.async_retry_pending()
    assert len(calls) == 1
    await restored.async_unload()
    again = WaterLeakManager(runtime_hass, runtime_entry)
    runtime_hass.data[DOMAIN][runtime_entry.entry_id] = again
    await again.async_setup()
    assert len(calls) == 1


async def test_f06_service_failure_isolated_and_retry_is_per_recipient(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "broken", "good")
    failed = [True]
    good_calls, broken_calls = [], []
    async def broken(call):
        if failed[0]:
            raise RuntimeError("send failed")
        broken_calls.append(call.data)
    async def good(call):
        good_calls.append(call.data)
    runtime_hass.services.async_register("notify", "mobile_app_broken", broken)
    runtime_hass.services.async_register("notify", "mobile_app_good", good)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    await activate(manager, runtime_hass, measurement_clock)
    assert len(good_calls) == 1
    failed[0] = False
    await manager.notifications.async_retry_pending()
    assert len(broken_calls) == 1
    assert len(good_calls) == 1


async def test_f10_lower_active_event_can_be_muted_without_changing_safety(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    manager.apply_options()
    manager.engine.update_settings(DetectorSettings(slow_detection_seconds=1, shutoff_slow=True))
    report(runtime_hass, measurement_clock, 7)
    await manager.async_refresh()
    measurement_clock.advance(1)
    report(runtime_hass, measurement_clock, 7)
    await manager.async_refresh()
    slow_id = manager.engine.runtimes[DetectorKind.SLOW_LEAK].event_id
    await activate(manager, runtime_hass, measurement_clock)
    runtime_hass.bus.async_fire(MOBILE_ACTION_EVENT, {
        "action": f"WLD|MUTE|{runtime_entry.entry_id}|{slow_id}|phone|token_phone",
    })
    await runtime_hass.async_block_till_done()
    assert "phone" in manager.notifications.acknowledgements[slow_id].muted_recipients
    assert manager.engine.runtimes[DetectorKind.SLOW_LEAK].event_id == slow_id
    assert manager.engine.snapshot().shutoff_request


async def test_f11_ack_during_translation_prevents_dispatch_to_every_recipient(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone", "tablet")
    calls = []
    async def notify(call):
        calls.append(call.data)
    for name in ("phone", "tablet"):
        runtime_hass.services.async_register("notify", f"mobile_app_{name}", notify)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    entered, release = asyncio.Event(), asyncio.Event()
    async def translations():
        entered.set()
        await release.wait()
        return {}
    manager.notifications._async_common_translations = translations
    event_id = await activate(manager, runtime_hass, measurement_clock, drain=False)
    await entered.wait()
    await manager.notifications._async_mobile_action(Event(MOBILE_ACTION_EVENT, {
        "action": f"WLD|ACK_ALL|{runtime_entry.entry_id}|{event_id}|phone|token_phone",
    }))
    release.set()
    await runtime_hass.async_block_till_done()
    assert not calls
    assert manager.engine.snapshot().alarm_active
    assert manager.engine.snapshot().shutoff_request


async def test_f11_removal_during_translation_prevents_old_route_send(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    calls = []
    async def notify(call):
        calls.append(call.data)
    runtime_hass.services.async_register("notify", "mobile_app_phone", notify)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    entered, release = asyncio.Event(), asyncio.Event()
    async def translations():
        entered.set()
        await release.wait()
        return {}
    manager.notifications._async_common_translations = translations
    await activate(manager, runtime_hass, measurement_clock, drain=False)
    await entered.wait()
    configure(runtime_hass, runtime_entry, measurement_clock)
    manager.notifications.reload_recipients()
    release.set()
    await runtime_hass.async_block_till_done()
    assert not calls


async def test_global_ack_survives_reload_and_prevents_retry(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    event_id = await activate(manager, runtime_hass, measurement_clock)
    await manager.notifications._async_mobile_action(Event(MOBILE_ACTION_EVENT, {
        "action": f"WLD|ACK_ALL|{runtime_entry.entry_id}|{event_id}|phone|token_phone",
    }))
    await manager.async_unload()
    calls = []
    async def notify(call):
        calls.append(call.data)
    runtime_hass.services.async_register("notify", "mobile_app_phone", notify)
    restored = WaterLeakManager(runtime_hass, runtime_entry)
    runtime_hass.data[DOMAIN][runtime_entry.entry_id] = restored
    await restored.async_setup()
    assert not calls
    assert restored.engine.snapshot().alarm_active
    assert restored.engine.snapshot().shutoff_request


async def test_f14_unload_cancels_inflight_delivery_and_all_listeners(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    entered = asyncio.Event()
    async def translations():
        entered.set()
        await asyncio.Event().wait()
    runtime_hass.services.async_register("notify", "mobile_app_phone", AsyncMock())
    manager.notifications._async_common_translations = translations
    await activate(manager, runtime_hass, measurement_clock, drain=False)
    await entered.wait()
    await manager.async_unload()
    assert not manager.notifications._delivery_tasks
    assert not manager.notifications._unsubs
    assert not manager._unsubs
    assert manager._save_handle is None


async def test_f06_new_event_does_not_inherit_acknowledgement_or_delivery(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    calls = []
    async def send(call):
        calls.append(call.data)
    runtime_hass.services.async_register("notify", "mobile_app_phone", send)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    old_id = await activate(manager, runtime_hass, measurement_clock)
    recipient_obj = manager.notifications.recipients["phone"]
    action = manager.notifications._action_id("ACK_ALL", old_id, recipient_obj)
    await manager.notifications._async_mobile_action(Event(MOBILE_ACTION_EVENT, {"action": action}))
    for _ in range(8):
        report(runtime_hass, measurement_clock, 0)
        await manager.async_refresh()
        await runtime_hass.async_block_till_done()
        measurement_clock.advance(10)
    assert not manager.engine.snapshot().alarm_active
    new_id = await activate(manager, runtime_hass, measurement_clock)
    assert new_id != old_id
    assert not manager.notifications.acknowledgements[new_id].globally_acknowledged
    assert len(calls) == 2


async def test_f11_end_during_translation_stops_pending_send_before_end_bus_handler(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    calls = []
    async def send(call):
        calls.append(call.data)
    runtime_hass.services.async_register("notify", "mobile_app_phone", send)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    entered, release = asyncio.Event(), asyncio.Event()
    async def translate():
        entered.set()
        await release.wait()
        return {}
    manager.notifications._async_common_translations = translate
    await activate(manager, runtime_hass, measurement_clock, drain=False)
    await entered.wait()
    runtime = manager.engine.runtimes[DetectorKind.BURST_LEAK]
    runtime.reset()  # Simulate engine transition before the asynchronous ended listener.
    release.set()
    await runtime_hass.async_block_till_done()
    assert calls == []


async def test_f06_periodic_retry_does_not_queue_behind_running_delivery(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    calls = []
    async def send(call):
        calls.append(call.data)
    runtime_hass.services.async_register("notify", "mobile_app_phone", send)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    entered, release = asyncio.Event(), asyncio.Event()
    async def translate():
        entered.set()
        await release.wait()
        return {}
    manager.notifications._async_common_translations = translate
    await activate(manager, runtime_hass, measurement_clock, drain=False)
    await entered.wait()
    for _ in range(10):
        await asyncio.wait_for(manager.notifications.async_retry_pending(), 0.1)
    assert len(manager.notifications._delivery_tasks) == 1
    release.set()
    await runtime_hass.async_block_till_done()
    assert len(calls) == 1
