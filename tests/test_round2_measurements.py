"""Round 2: real report cadence, UTC corrections and shared total references."""

from datetime import timedelta

import pytest
from homeassistant.core import Event
from test_manager_runtime import report, start_manager

from custom_components.water_leak_detection.const import DOMAIN, DetectorKind, DetectorPhase
from custom_components.water_leak_detection.engine import DetectionEngine, DetectorSettings
from custom_components.water_leak_detection.manager import WaterLeakManager
from custom_components.water_leak_detection.sensor import ActiveEventDurationSensor


async def fresh(hass, manager, clock, flow):
    report(hass, clock, flow)
    await manager.async_refresh()
    await hass.async_block_till_done()


@pytest.mark.parametrize("period", [5, 30, 60, 120, 600])
@pytest.mark.parametrize("kind,flow", [
    (DetectorKind.SLOW_LEAK, 7), (DetectorKind.LOW_FLOW, 200),
    (DetectorKind.HIGH_FLOW, 800), (DetectorKind.BURST_LEAK, 2500),
])
async def test_f05_cadence_works_with_internal_ticks_and_identical_reports(
    runtime_hass, runtime_entry, measurement_clock, period, kind, flow
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, flow)
    manager.engine.update_settings(DetectorSettings(
        slow_detection_seconds=period * 2, low_detection_seconds=period * 2,
        high_detection_seconds=period * 2,
    ))
    last_updated = runtime_hass.states.get("sensor.flow").last_updated
    for _ in range(max(5, 30 // period + 2)):
        previous = manager.engine.last_sample_at
        for _ in range(period // 5):
            measurement_clock.advance(5)
            await manager._async_tick(measurement_clock.utcnow())
            # During unqualified very slow startup, expiry may suspend the
            # old observation. It must never advance a timer from an internal tick.
            assert manager.engine.last_sample_at in (previous, None)
        await fresh(runtime_hass, manager, measurement_clock, flow)
    assert runtime_hass.states.get("sensor.flow").last_updated == last_updated
    assert manager.engine.runtimes[kind].phase is DetectorPhase.ACTIVE


@pytest.mark.parametrize("kind,flow", [
    (DetectorKind.SLOW_LEAK, 7), (DetectorKind.LOW_FLOW, 200),
    (DetectorKind.HIGH_FLOW, 800), (DetectorKind.BURST_LEAK, 2500),
])
async def test_f05_single_frozen_report_never_activates_or_resets(
    runtime_hass, runtime_entry, measurement_clock, kind, flow
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, flow)
    manager.engine.update_settings(DetectorSettings(
        slow_detection_seconds=10, low_detection_seconds=10, high_detection_seconds=10,
        shutoff_slow=True, shutoff_low=True, shutoff_high=True,
    ))
    for _ in range(75):
        measurement_clock.advance(5)
        await manager._async_tick(measurement_clock.utcnow())
    assert not manager.engine.snapshot().alarm_active
    for _ in range(6):
        measurement_clock.advance(10)
        await fresh(runtime_hass, manager, measurement_clock, flow)
    event_id = manager.engine.runtimes[kind].event_id
    assert event_id
    measurement_clock.advance(10)
    await fresh(runtime_hass, manager, measurement_clock, 0)
    for _ in range(100):
        measurement_clock.advance(10)
        await manager._async_tick(measurement_clock.utcnow())
    assert manager.engine.runtimes[kind].event_id == event_id
    assert manager.engine.snapshot().shutoff_request
    assert manager.engine.runtimes[kind].quiet_since is None


async def test_f05_outage_is_not_learned_as_normal_cadence(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    for _ in range(4):
        measurement_clock.advance(60)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    measurement_clock.advance(3600)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    runtime = manager.engine.runtimes[DetectorKind.HIGH_FLOW]
    assert runtime.phase is DetectorPhase.MONITORING
    assert runtime.started_at == manager.timer_now
    assert runtime.estimated_volume_l == 0
    assert max(manager._flow_evidence.intervals) == 60
    assert manager._flow_evidence.credited_seconds == 0


@pytest.mark.parametrize("shift", [-3600, 3600])
async def test_f15_utc_correction_reports_duration_quiet_bypass_and_reload(
    runtime_hass, runtime_entry, measurement_clock, shift
):
    manager = await start_manager(
        runtime_hass, runtime_entry, measurement_clock, 2500, configured_gap=10
    )
    for _ in range(3):
        measurement_clock.advance(10)
        await fresh(runtime_hass, manager, measurement_clock, 2500)
    event_id = manager.engine.snapshot().active_event_id
    sensor = ActiveEventDurationSensor(manager)
    before_duration = sensor.native_value
    await manager.async_start_bypass(2)
    measurement_clock.wall_shift += shift
    for _ in range(3):
        measurement_clock.advance(10)
        await fresh(runtime_hass, manager, measurement_clock, 2500)
    assert sensor.native_value == before_duration + 30
    assert manager.bypass_remaining_seconds == 90
    assert manager.engine.snapshot().active_event_id == event_id
    duration = sensor.native_value
    await manager.async_unload()
    restored = WaterLeakManager(runtime_hass, runtime_entry)
    runtime_hass.data[DOMAIN][runtime_entry.entry_id] = restored
    await restored.async_setup()
    assert restored.engine.snapshot().active_event_id == event_id
    assert restored.event_elapsed_seconds(event_id) == duration
    assert restored.bypass_remaining_seconds == 90
    measurement_clock.advance(10)
    await fresh(runtime_hass, restored, measurement_clock, 0)
    quiet_since = restored.engine.runtimes[DetectorKind.BURST_LEAK].quiet_since
    assert quiet_since
    measurement_clock.wall_shift -= shift * 2
    for _ in range(5):
        measurement_clock.advance(10)
        await fresh(runtime_hass, restored, measurement_clock, 0)
        assert restored.engine.runtimes[DetectorKind.BURST_LEAK].event_id == event_id
    measurement_clock.advance(10)
    await fresh(runtime_hass, restored, measurement_clock, 0)
    assert restored.engine.runtimes[DetectorKind.BURST_LEAK].phase is DetectorPhase.IDLE
    measurement_clock.advance(31)
    assert not restored.high_flow_bypass_active


async def test_f15_queued_old_event_is_rejected_by_identity_after_clock_rollback(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    old = runtime_hass.states.get("sensor.flow")
    measurement_clock.advance(10)
    measurement_clock.wall_shift -= 3600
    await fresh(runtime_hass, manager, measurement_clock, 2500)
    before = manager.engine.to_dict()
    await manager._async_source_changed(Event("state_changed", {
        "entity_id": "sensor.flow", "new_state": old,
    }))
    assert manager.engine.to_dict() == before
    assert manager.current_flow_lph == 2500


@pytest.mark.parametrize("quantum", [None, 1, 10, 100])
@pytest.mark.parametrize("total_period", [5, 60, 120])
def test_f07_continuous_and_quantized_totals_across_different_cadences(quantum, total_period):
    engine = DetectionEngine(DetectorSettings(high_volume_l=10_000))
    origin = measurement_origin()
    total = 1000.0
    for second in range(0, 1201, 5):
        volume = 800 * second / 3600
        if second % total_period == 0:
            total = 1000 + (volume if quantum is None else int(volume // quantum) * quantum)
        engine.sample(origin + timedelta(seconds=second), 800, total)
    assert engine.last_total_l == total
    assert engine._event_volume(engine.runtimes[DetectorKind.HIGH_FLOW], total) >= 266
    assert engine.runtimes[DetectorKind.HIGH_FLOW].phase is DetectorPhase.MONITORING


def measurement_origin():
    from datetime import UTC, datetime
    return datetime(2026, 10, 7, tzinfo=UTC)


@pytest.mark.parametrize("replacement", [0, 500, 1_000_000])
def test_f07_reset_negative_and_unrealistic_jump_cannot_add_alarm_volume(replacement):
    engine = DetectionEngine(DetectorSettings(high_volume_l=100))
    origin = measurement_origin()
    engine.sample(origin, 800, 1000)
    for second in range(5, 61, 5):
        engine.sample(origin + timedelta(seconds=second), 800, replacement)
    assert not engine.snapshot(replacement).alarm_active
    assert engine._event_volume(engine.runtimes[DetectorKind.HIGH_FLOW], replacement) < 14


def test_f07_pending_quantum_keeps_common_reference_until_flow_supports_it():
    engine = DetectionEngine(DetectorSettings(high_volume_l=500))
    origin = measurement_origin()
    engine.sample(origin, 800, 1000)
    engine.sample(origin + timedelta(seconds=5), 800, 1100)
    assert engine.last_total_l == 1000
    for second in range(10, 451, 5):
        engine.sample(origin + timedelta(seconds=second), 800, 1100)
    # F07 Round 3: cached pending progress needs a new actual total report.
    assert engine.last_total_l == 1000
    engine.sample(origin + timedelta(seconds=455), 800, 1100, total_fresh=True)
    assert engine.last_total_l == 1100
    assert not engine.snapshot(1100).alarm_active


def test_f07_absence_and_return_rebase_without_unknown_volume():
    engine = DetectionEngine()
    origin = measurement_origin()
    engine.sample(origin, 800, 1000)
    engine.sample(origin + timedelta(seconds=5), 800, None)
    engine.sample(origin + timedelta(seconds=10), 800, 1_000_000)
    assert engine.last_total_l == 1_000_000
    assert engine._event_volume(engine.runtimes[DetectorKind.HIGH_FLOW], 1_000_000) < 3


async def test_f05_missing_two_regular_reports_does_not_credit_unknown_gap(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    for _ in range(3):
        measurement_clock.advance(60)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    measurement_clock.advance(120)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    runtime = manager.engine.runtimes[DetectorKind.HIGH_FLOW]
    assert runtime.started_at == manager.timer_now
    assert runtime.estimated_volume_l == 0


async def test_f15_event_utc_labels_stay_real_while_timers_are_monotonic(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(
        runtime_hass, runtime_entry, measurement_clock, 2500, configured_gap=10
    )
    started_utc = measurement_clock.utcnow()
    measurement_clock.wall_shift -= 3600
    for _ in range(3):
        measurement_clock.advance(10)
        await fresh(runtime_hass, manager, measurement_clock, 2500)
    snapshot = manager.engine.snapshot()
    assert snapshot.active_started_at == started_utc
    assert snapshot.active_detected_at == measurement_clock.utcnow()
    assert manager.event_elapsed_seconds(snapshot.active_event_id) == 30
    persisted = manager._serialize()["engine"]["runtimes"]["burst_leak"]
    assert persisted["detected_at"] == measurement_clock.utcnow().isoformat()
    assert persisted["started_at"] == started_utc.isoformat()


async def test_f15_same_utc_timestamp_report_after_clock_rollback_is_still_new(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(
        runtime_hass, runtime_entry, measurement_clock, 2500, configured_gap=10
    )
    for _ in range(3):
        measurement_clock.advance(10)
        await fresh(runtime_hass, manager, measurement_clock, 2500)
    previous = runtime_hass.states.get("sensor.flow").last_reported
    measurement_clock.advance(10)
    measurement_clock.wall_shift -= 10
    await fresh(runtime_hass, manager, measurement_clock, 2500)
    assert runtime_hass.states.get("sensor.flow").last_reported == previous
    assert manager.engine.last_sample_at == manager.timer_now
    assert manager.event_elapsed_seconds(manager.engine.snapshot().active_event_id) == 40


@pytest.mark.parametrize("invalid", ["unknown", "unavailable", "bad", "-1"])
async def test_f07_total_outage_between_flow_reports_rebases_on_return(
    runtime_hass, runtime_entry, measurement_clock, invalid
):
    runtime_hass.config_entries.async_update_entry(runtime_entry, data={
        "flow_entity": "sensor.flow", "total_entity": "sensor.total",
    })
    report(runtime_hass, measurement_clock, 1000, "sensor.total", "L")
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    measurement_clock.advance(5)
    report(runtime_hass, measurement_clock, invalid, "sensor.total", "L")
    await runtime_hass.async_block_till_done()
    assert manager.engine.last_total_l is None
    report(runtime_hass, measurement_clock, 1_000_000, "sensor.total", "L")
    await runtime_hass.async_block_till_done()
    measurement_clock.advance(5)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    assert manager.engine.last_total_l == 1_000_000
    assert not manager.engine.snapshot(1_000_000).alarm_active


async def test_f15_bypass_persistence_preserves_fractional_monotonic_remaining_time(
    runtime_hass, runtime_entry, measurement_clock
):
    from custom_components.water_leak_detection.validation import parse_datetime
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 7)
    await manager.async_start_bypass(2)
    measurement_clock.advance(10.25)
    measurement_clock.wall_shift -= 3600
    expiry = parse_datetime(manager._serialize()["bypass_until"])
    assert (expiry - measurement_clock.utcnow()).total_seconds() == 109.75
    assert manager.bypass_remaining_seconds == 109


async def test_f05_round1_persisted_default_does_not_break_sixty_second_upgrade(
    runtime_hass, runtime_entry, measurement_clock
):
    runtime_hass.config_entries.async_update_entry(runtime_entry, options={
        "source_max_age_seconds": 30,
    })
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 2500)
    assert manager.source_max_age_seconds == 0
    for _ in range(3):
        measurement_clock.advance(60)
        await fresh(runtime_hass, manager, measurement_clock, 2500)
    assert manager.engine.snapshot().alarm_active


async def test_f05_expert_flow_distinguishes_legacy_default_from_explicit_thirty_seconds(
    runtime_hass, runtime_entry
):
    from test_config_runtime import options_flow
    runtime_hass.config_entries.async_update_entry(runtime_entry, options={
        "source_max_age_seconds": 30,
    })
    flow = options_flow(runtime_hass, runtime_entry)
    form = await flow.async_step_expert()
    values = form["data_schema"]({})
    assert values["source_max_age_seconds"] == 0
    values["source_max_age_seconds"] = 30
    result = await flow.async_step_expert(values)
    assert result["step_id"] == "init"
    assert runtime_entry.options["source_gap_policy_explicit"] is True
    manager = WaterLeakManager(runtime_hass, runtime_entry)
    assert manager.source_max_age_seconds == 30


async def test_f05_other_positive_legacy_limits_are_preserved(runtime_hass, runtime_entry):
    runtime_hass.config_entries.async_update_entry(runtime_entry, options={
        "source_max_age_seconds": 120,
    })
    assert WaterLeakManager(runtime_hass, runtime_entry).source_max_age_seconds == 120
