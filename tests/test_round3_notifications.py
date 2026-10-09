"""Per-route dispatch persistence and bounded cleanup of ended-event workers."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import Event, State
from test_manager_runtime import report, start_manager
from test_notification_runtime import activate, configure

from custom_components.water_leak_detection.const import (
    CONF_NOTIFICATION_RECIPIENTS,
    DOMAIN,
    DetectorKind,
    DetectorPhase,
)
from custom_components.water_leak_detection.manager import WaterLeakManager
from custom_components.water_leak_detection.notifications import DispatchState


@pytest.mark.parametrize("status", [DispatchState.INTERRUPTED, DispatchState.ACCEPTED])
@pytest.mark.parametrize("new_service", [False, True])
@pytest.mark.parametrize("restore", [False, True])
async def test_f06_status_only_blocks_its_concrete_route(
    runtime_hass, runtime_entry, measurement_clock, status, new_service, restore
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    event_id = await activate(manager, runtime_hass, measurement_clock)
    controller = manager.notifications
    phone = controller.recipients["phone"]
    old_route = controller._delivery_key(phone)
    state = controller.acknowledgements[event_id]
    state.route_states[old_route] = status.value
    state.dispatch_states["phone"] = status.value
    if status is DispatchState.ACCEPTED:
        state.accepted_recipients["phone"] = old_route
    if restore:
        await manager.async_unload()
    options = dict(runtime_entry.options)
    recipient = dict(options[CONF_NOTIFICATION_RECIPIENTS][0])
    if new_service:
        recipient["notify_service"] = "notify.mobile_app_new"
    options[CONF_NOTIFICATION_RECIPIENTS] = [recipient]
    runtime_hass.config_entries.async_update_entry(runtime_entry, options=options)
    calls = []

    async def notify(call):
        calls.append(call.service)

    runtime_hass.services.async_register("notify", "mobile_app_phone", notify)
    runtime_hass.services.async_register("notify", "mobile_app_new", notify)
    if restore:
        report(runtime_hass, measurement_clock, 2500)
        manager = WaterLeakManager(runtime_hass, runtime_entry)
        manager.notifications._async_common_translations = AsyncMock(return_value={})
        runtime_hass.data[DOMAIN][runtime_entry.entry_id] = manager
        await manager.async_setup()
    else:
        manager.apply_options()
    for _ in range(5):
        await manager.notifications.async_retry_pending()
    await runtime_hass.async_block_till_done()
    assert calls == (["mobile_app_new"] if new_service else [])
    assert manager.engine.snapshot().active_event_id == event_id
    assert manager.engine.snapshot().shutoff_request
    # Returning Home cannot apply the old route's interruption to a new route.
    if new_service and status is DispatchState.INTERRUPTED:
        await manager.notifications._async_tracker_changed(
            Event(
                "state_changed",
                {
                    "entity_id": "device_tracker.phone",
                    "old_state": State("device_tracker.phone", "away"),
                    "new_state": State("device_tracker.phone", "home"),
                },
            )
        )
        await runtime_hass.async_block_till_done()
        assert calls == ["mobile_app_new", "mobile_app_new"]


async def test_f06_new_route_does_not_override_global_ack(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    event_id = await activate(manager, runtime_hass, measurement_clock)
    state = manager.notifications.acknowledgements[event_id]
    state.globally_acknowledged = True
    old_route = manager.notifications._delivery_key(manager.notifications.recipients["phone"])
    state.route_states[old_route] = DispatchState.INTERRUPTED.value
    options = dict(runtime_entry.options)
    options[CONF_NOTIFICATION_RECIPIENTS][0] = {
        **options[CONF_NOTIFICATION_RECIPIENTS][0],
        "notify_service": "notify.mobile_app_new",
    }
    runtime_hass.config_entries.async_update_entry(runtime_entry, options=options)
    calls = []

    async def notify(call):
        calls.append(call)

    runtime_hass.services.async_register("notify", "mobile_app_new", notify)
    manager.apply_options()
    await runtime_hass.async_block_till_done()
    assert not calls
    assert manager.engine.snapshot().shutoff_request
    assert manager.engine.snapshot().active_event_id == event_id


@pytest.mark.parametrize("recipients", [("one",), ("one", "two")])
@pytest.mark.parametrize("second_event", [False, True])
async def test_f06_ended_event_cancels_only_its_dispatch_tasks(
    runtime_hass, runtime_entry, measurement_clock, recipients, second_event
):
    configure(runtime_hass, runtime_entry, measurement_clock, *recipients)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    controller = manager.notifications
    release = asyncio.Event()
    entered = set()

    async def hanging(call):
        entered.add((call.data["data"]["wld_event_id"], call.service))
        await release.wait()

    for name in recipients:
        runtime_hass.services.async_register("notify", f"mobile_app_{name}", hanging)
    kinds = (
        [DetectorKind.BURST_LEAK, DetectorKind.HIGH_FLOW]
        if second_event
        else [DetectorKind.BURST_LEAK]
    )
    for kind in kinds:
        runtime = manager.engine.runtimes[kind]
        runtime.phase = DetectorPhase.ACTIVE
        runtime.event_id = f"{kind.value}_cleanup"
        await controller._async_leak_started(
            Event(
                "started",
                {
                    "config_entry_id": runtime_entry.entry_id,
                    "event_id": runtime.event_id,
                    "type": kind.value,
                },
            )
        )
    for _ in range(20):
        await asyncio.sleep(0)
        if len(entered) == len(kinds) * len(recipients):
            break
    assert len(entered) == len(kinds) * len(recipients)
    ended_id = manager.engine.runtimes[DetectorKind.BURST_LEAK].event_id
    manager.engine.runtimes[DetectorKind.BURST_LEAK].reset()
    await asyncio.wait_for(
        controller._async_leak_ended(
            Event(
                "ended",
                {
                    "config_entry_id": runtime_entry.entry_id,
                    "event_id": ended_id,
                },
            )
        ),
        1,
    )
    assert ended_id not in controller._events
    assert ended_id not in controller.acknowledgements
    assert all(identity[0] != ended_id for identity in controller._dispatch_tasks)
    assert len(controller._delivery_tasks) == (len(recipients) if second_event else 0)
    release.set()
    await runtime_hass.async_block_till_done()
    assert not controller._delivery_tasks
    assert not controller._dispatch_tasks
    assert ended_id not in controller.acknowledgements


@pytest.mark.parametrize("after_service_return", [False, True])
async def test_f06_ending_worker_start_or_service_return_cannot_resurrect_event(
    runtime_hass, runtime_entry, measurement_clock, after_service_return
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    event_id = await activate(manager, runtime_hass, measurement_clock)
    controller = manager.notifications
    calls = []

    async def notify(call):
        calls.append(call)
        manager.engine.runtimes[DetectorKind.BURST_LEAK].reset()
        # End can run immediately after HA accepted the call, before worker completion.
        runtime_hass.async_create_task(
            controller._async_leak_ended(
                Event(
                    "ended",
                    {
                        "config_entry_id": runtime_entry.entry_id,
                        "event_id": event_id,
                    },
                )
            )
        )

    runtime_hass.services.async_register("notify", "mobile_app_phone", notify)
    retry = asyncio.create_task(controller.async_retry_pending())
    if not after_service_return:
        manager.engine.runtimes[DetectorKind.BURST_LEAK].reset()
        await controller._async_leak_ended(
            Event(
                "ended",
                {
                    "config_entry_id": runtime_entry.entry_id,
                    "event_id": event_id,
                },
            )
        )
    await retry
    await runtime_hass.async_block_till_done()
    assert len(calls) == int(after_service_return)
    assert event_id not in controller._events
    assert event_id not in controller.acknowledgements
    assert not controller._dispatch_tasks
    assert not controller._delivery_tasks


async def test_f06_new_route_can_dispatch_while_old_route_is_in_flight(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    old_entered, old_release, new_done = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = []

    async def old(call):
        calls.append("old")
        old_entered.set()
        await old_release.wait()

    async def new(call):
        calls.append("new")
        new_done.set()

    runtime_hass.services.async_register("notify", "mobile_app_phone", old)
    runtime_hass.services.async_register("notify", "mobile_app_new", new)
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 0)
    event_id = await activate(manager, runtime_hass, measurement_clock, drain=False)
    await asyncio.wait_for(old_entered.wait(), 1)
    options = dict(runtime_entry.options)
    options[CONF_NOTIFICATION_RECIPIENTS] = [
        {
            **options[CONF_NOTIFICATION_RECIPIENTS][0],
            "notify_service": "notify.mobile_app_new",
        }
    ]
    runtime_hass.config_entries.async_update_entry(runtime_entry, options=options)
    manager.apply_options()
    await asyncio.wait_for(new_done.wait(), 1)
    for _ in range(5):
        await manager.notifications.async_retry_pending()
    assert calls == ["old", "new"]
    old_release.set()
    await runtime_hass.async_block_till_done()
    state = manager.notifications.acknowledgements[event_id]
    assert len(state.route_states) == 2
    assert set(state.route_states.values()) == {DispatchState.ACCEPTED}
    await manager.notifications.async_retry_pending()
    await runtime_hass.async_block_till_done()
    assert calls == ["old", "new"]


async def test_f06_legacy_interruption_cannot_be_falsely_bound_to_new_service_on_restore(
    runtime_hass, runtime_entry, measurement_clock
):
    configure(runtime_hass, runtime_entry, measurement_clock, "phone")
    options = dict(runtime_entry.options)
    options[CONF_NOTIFICATION_RECIPIENTS] = [
        {
            **options[CONF_NOTIFICATION_RECIPIENTS][0],
            "notify_service": "notify.mobile_app_new",
        }
    ]
    runtime_hass.config_entries.async_update_entry(runtime_entry, options=options)
    manager = WaterLeakManager(runtime_hass, runtime_entry)
    now = measurement_clock.utcnow().isoformat()
    await manager._store.async_save(
        {
            "engine": {
                "runtimes": {
                    "burst_leak": {
                        "phase": "active",
                        "event_id": "burst_leak_legacy",
                        "started_at": now,
                        "detected_at": now,
                    }
                }
            },
            "acknowledgements": {"burst_leak_legacy": {"dispatch_states": {"phone": "in_flight"}}},
        }
    )
    calls = []

    async def notify(call):
        calls.append(call.service)

    runtime_hass.services.async_register("notify", "mobile_app_new", notify)
    manager.notifications._async_common_translations = AsyncMock(return_value={})
    report(runtime_hass, measurement_clock, "unavailable")
    runtime_hass.data.setdefault(DOMAIN, {})[runtime_entry.entry_id] = manager
    await manager.async_setup()
    await runtime_hass.async_block_till_done()
    assert calls == ["mobile_app_new"]
    routes = manager.notifications.acknowledgements["burst_leak_legacy"].route_states
    assert routes['["phone",null]'] == DispatchState.INTERRUPTED
    assert routes['["phone","notify.mobile_app_new"]'] == DispatchState.ACCEPTED
    assert manager.engine.snapshot().shutoff_request
