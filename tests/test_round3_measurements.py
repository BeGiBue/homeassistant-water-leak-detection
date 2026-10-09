"""Non-retroactive cadence evidence, independent controls and real UTC history."""

from datetime import timedelta

import pytest
from test_manager_runtime import report, start_manager
from test_notification_runtime import configure
from test_round2_measurements import fresh, measurement_origin

from custom_components.water_leak_detection.const import (
    CONF_FLOW_ENTITY,
    CONF_HIGH_VOLUME_L,
    CONF_TOTAL_ENTITY,
    DOMAIN,
    DetectorKind,
    DetectorPhase,
)
from custom_components.water_leak_detection.engine import DetectionEngine, DetectorSettings
from custom_components.water_leak_detection.manager import WaterLeakManager


@pytest.mark.parametrize("cadence", [5, 30, 60, 120, 600, (60, 120), (600, 120)])
async def test_f05_constant_and_alternating_reports_reach_detection_without_tick_credit(
    runtime_hass, runtime_entry, measurement_clock, cadence
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=3600, high_volume_l=99999)
    )
    periods = cadence if isinstance(cadence, tuple) else (cadence,)
    while measurement_clock.seconds < 14400:
        # Explicit alternation independent of whether periods are even numbers.
        index = getattr(manager, "_test_report_index", 0)
        period = periods[index % len(periods)]
        manager._test_report_index = index + 1
        before = manager.engine.last_sample_at
        for _ in range(period // 5):
            measurement_clock.advance(5)
            await manager._async_tick(measurement_clock.utcnow())
            assert manager.engine.last_sample_at == before
        await fresh(runtime_hass, manager, measurement_clock, 800)
        if manager.engine.snapshot().alarm_active and len(periods) == 1:
            break
    assert manager.engine.runtimes[DetectorKind.HIGH_FLOW].phase is DetectorPhase.ACTIVE
    assert measurement_clock.seconds >= 3600


async def test_f05_five_second_cadence_cannot_retroactively_credit_240_second_gap(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=200, high_volume_l=99999)
    )
    for _ in range(3):
        measurement_clock.advance(5)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    for _ in range(2):
        measurement_clock.advance(240)
        await fresh(runtime_hass, manager, measurement_clock, 800)
        assert manager._flow_evidence.credited_seconds == 0
        assert not manager.engine.snapshot().alarm_active
    measurement_clock.advance(5)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    assert not manager.engine.snapshot().alarm_active
    assert manager.engine.runtimes[DetectorKind.HIGH_FLOW].estimated_volume_l < 2


@pytest.mark.parametrize("gap", [120, 7200])
async def test_f05_missing_reports_delay_detection_without_crediting_unknown_time(
    runtime_hass, runtime_entry, measurement_clock, gap
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=180, high_volume_l=99999)
    )
    for _ in range(3):
        measurement_clock.advance(60)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    measurement_clock.advance(gap)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    assert manager._flow_evidence.credited_seconds == 0
    assert not manager.engine.snapshot().alarm_active
    for _ in range(6):
        measurement_clock.advance(60)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    assert manager.engine.snapshot().alarm_active


@pytest.mark.parametrize("flow", [0, 800])
async def test_f05_frozen_states_supply_no_time_but_identical_reports_do(
    runtime_hass, runtime_entry, measurement_clock, flow
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=20, high_reset_seconds=20)
    )
    for _ in range(4):
        measurement_clock.advance(5)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    event_id = manager.engine.snapshot().active_event_id
    assert event_id
    measurement_clock.advance(5)
    await fresh(runtime_hass, manager, measurement_clock, flow)
    for _ in range(200):
        measurement_clock.advance(5)
        await manager._async_tick(measurement_clock.utcnow())
    assert manager.engine.snapshot().active_event_id == event_id
    if flow == 0:
        for _ in range(6):
            measurement_clock.advance(5)
            await fresh(runtime_hass, manager, measurement_clock, 0)
        assert not manager.engine.snapshot().alarm_active


@pytest.mark.parametrize(
    "control", ["slow_disable", "low_disable", "bypass", "recipients", "options"]
)
async def test_f12_frozen_source_does_not_block_controls(
    runtime_hass, runtime_entry, measurement_clock, control
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    kind = (
        DetectorKind.SLOW_LEAK
        if control == "slow_disable"
        else (DetectorKind.LOW_FLOW if control == "low_disable" else DetectorKind.HIGH_FLOW)
    )
    runtime = manager.engine.runtimes[kind]
    runtime.phase = DetectorPhase.ACTIVE
    runtime.event_id = f"{kind.value}_control"
    runtime.started_at = manager.timer_now
    runtime.detected_at = manager.timer_now
    before_sample = manager.engine.last_sample_at
    if control.endswith("disable"):
        await manager.async_set_detector_enabled(control.split("_")[0], False)
        assert runtime.phase is DetectorPhase.IDLE
    elif control == "bypass":
        await manager.async_start_bypass(5)
        assert runtime.phase is DetectorPhase.IDLE
        await manager.async_cancel_bypass()
        assert runtime.phase is DetectorPhase.IDLE
    elif control == "recipients":
        configure(runtime_hass, runtime_entry, measurement_clock, "new")
        manager.apply_options()
        assert set(manager.notifications.recipients) == {"new"}
        assert runtime.phase is DetectorPhase.ACTIVE
    else:
        runtime_hass.config_entries.async_update_entry(
            runtime_entry, options={CONF_HIGH_VOLUME_L: 999}
        )
        manager.apply_options()
        assert manager.engine.settings.high_volume_l == 999
        assert runtime.phase is DetectorPhase.ACTIVE
    assert manager.engine.last_sample_at == before_sample
    await runtime_hass.async_block_till_done()


@pytest.mark.parametrize("fresh_total", [False, True])
def test_f07_rejected_total_requires_new_total_confirmation_and_no_flow_shortcut(fresh_total):
    engine = DetectionEngine(DetectorSettings(high_volume_l=100, high_detection_seconds=99999))
    origin = measurement_origin()
    engine.sample(origin, 800, 1000)
    engine.sample(origin + timedelta(seconds=5), 800, 1100)
    for second in range(10, 451, 5):
        engine.sample(origin + timedelta(seconds=second), 800, 1100)
        if second < 450:
            assert not engine.snapshot().alarm_active
    assert engine.last_total_l == 1000
    engine.sample(origin + timedelta(seconds=455), 800, 1100, total_fresh=fresh_total)
    assert engine.last_total_l == (1100 if fresh_total else 1000)
    # Flow remains independently usable even when the suspicious total stays frozen.
    assert engine.snapshot().alarm_active


@pytest.mark.parametrize("quantum", [1, 10, 100])
@pytest.mark.parametrize("total_period", [5, 60, 120])
def test_f07_quantized_progress_keeps_unused_flow_credit(quantum, total_period):
    engine = DetectionEngine(DetectorSettings(high_volume_l=99999))
    origin = measurement_origin()
    total = 1000
    for second in range(0, 1801, 5):
        total_fresh = second % total_period == 0
        if total_fresh:
            total = 1000 + int((800 * second / 3600) // quantum) * quantum
        engine.sample(origin + timedelta(seconds=second), 800, total, total_fresh=total_fresh)
    assert engine.last_total_l == total
    assert engine._event_volume(engine.runtimes[DetectorKind.HIGH_FLOW], total) >= 399


async def test_f07_manager_tracks_total_report_freshness_separately_from_flow(
    runtime_hass, runtime_entry, measurement_clock
):
    runtime_hass.config_entries.async_update_entry(
        runtime_entry, data={CONF_FLOW_ENTITY: "sensor.flow", CONF_TOTAL_ENTITY: "sensor.total"}
    )
    report(runtime_hass, measurement_clock, 1000, "sensor.total", "L")
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    measurement_clock.advance(5)
    report(runtime_hass, measurement_clock, 1100, "sensor.total", "L")
    await fresh(runtime_hass, manager, measurement_clock, 800)
    for _ in range(100):
        measurement_clock.advance(5)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    assert manager.engine.last_total_l == 1000
    report(runtime_hass, measurement_clock, 1100, "sensor.total", "L")
    await runtime_hass.async_block_till_done()
    measurement_clock.advance(5)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    assert manager.engine.last_total_l == 1100


@pytest.mark.parametrize("shifts", [(-3600,), (3600,), (-3600, 7200, -3600)])
async def test_f15_real_utc_learning_history_survives_unload_restore_and_window(
    runtime_hass, runtime_entry, measurement_clock, shifts
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 50)
    for shift in shifts:
        measurement_clock.wall_shift += shift
        measurement_clock.advance(5)
        await fresh(runtime_hass, manager, measurement_clock, 50)
    for _ in range(25):
        measurement_clock.advance(5)
        await fresh(runtime_hass, manager, measurement_clock, 0)
    assert len(manager.learner.samples) == 1
    timestamp = manager.learner.samples[0].timestamp
    assert timestamp == measurement_clock.utcnow()
    assert manager.timer_now - timestamp == timedelta(seconds=-sum(shifts))
    await manager.async_unload()
    restored = WaterLeakManager(runtime_hass, runtime_entry)
    runtime_hass.data[DOMAIN][runtime_entry.entry_id] = restored
    await restored.async_setup()
    assert restored.learner.samples[0].timestamp == timestamp
    assert restored.learner.snapshot(timestamp + timedelta(days=29)).sample_count == 1
    assert restored.learner.snapshot(timestamp + timedelta(days=31)).sample_count == 0


@pytest.mark.parametrize("shift", [-3600, 3600])
async def test_f15_learning_quiet_timer_is_monotonic_and_admission_is_actual_utc(
    runtime_hass, runtime_entry, measurement_clock, shift
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 50)
    measurement_clock.advance(5)
    await fresh(runtime_hass, manager, measurement_clock, 0)
    measurement_clock.wall_shift += shift
    for _ in range(23):
        measurement_clock.advance(5)
        await fresh(runtime_hass, manager, measurement_clock, 0)
        assert not manager.learner.samples
    measurement_clock.advance(5)
    await fresh(runtime_hass, manager, measurement_clock, 0)
    assert manager.learner.samples[0].timestamp == measurement_clock.utcnow()


@pytest.mark.parametrize("replacement", [0, 500, None])
def test_f07_reset_or_outage_discards_suspicious_pending_reference(replacement):
    engine = DetectionEngine(DetectorSettings(high_volume_l=100, high_detection_seconds=99999))
    origin = measurement_origin()
    engine.sample(origin, 800, 1000)
    engine.sample(origin + timedelta(seconds=5), 800, 1100)
    assert engine.last_total_l == 1000
    engine.sample(origin + timedelta(seconds=10), 800, replacement)
    assert engine.last_total_l == replacement
    engine.sample(origin + timedelta(seconds=15), 800, 1_000_000)
    assert not engine.snapshot(1_000_000).alarm_active
    assert engine._event_volume(engine.runtimes[DetectorKind.HIGH_FLOW], 1_000_000) < 4


def test_f07_later_quantum_still_needs_new_total_confirmation():
    engine = DetectionEngine(DetectorSettings(high_volume_l=500, high_detection_seconds=99999))
    origin = measurement_origin()
    engine.sample(origin, 800, 1000)
    engine.sample(origin + timedelta(seconds=5), 800, 1100)
    for second in range(10, 901, 5):
        total = 1100 if second < 450 else 1200
        engine.sample(origin + timedelta(seconds=second), 800, total, total_fresh=False)
    # The new quantum at 450 s was still unsupported; its cached value remains rejected.
    assert engine.last_total_l == 1000
    engine.sample(origin + timedelta(seconds=905), 800, 1200, total_fresh=True)
    assert engine.last_total_l == 1200
    assert not engine.snapshot().alarm_active


async def test_f05_alternating_modes_do_not_credit_an_unseen_180_second_gap(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    for period in (60, 120) * 4:
        measurement_clock.advance(period)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    assert max(manager._flow_evidence.intervals) == 120
    measurement_clock.advance(180)  # A missing short report is not a new cadence.
    await fresh(runtime_hass, manager, measurement_clock, 800)
    assert manager._flow_evidence.credited_seconds == 0
    assert manager.engine.runtimes[DetectorKind.HIGH_FLOW].estimated_volume_l == 0


async def test_f05_missing_five_second_report_is_not_bootstrap_fast_evidence(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    for _ in range(3):
        measurement_clock.advance(5)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    measurement_clock.advance(10)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    assert manager._flow_evidence.credited_seconds == 0
    assert manager.engine.runtimes[DetectorKind.HIGH_FLOW].estimated_volume_l == 0


async def test_f05_rare_gaps_separated_by_regular_reports_do_not_qualify_a_mode(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    for _ in range(2):
        for _ in range(10):
            measurement_clock.advance(5)
            await fresh(runtime_hass, manager, measurement_clock, 800)
        measurement_clock.advance(240)
        await fresh(runtime_hass, manager, measurement_clock, 800)
        assert manager._flow_evidence.credited_seconds == 0
    assert max(manager._flow_evidence.intervals) == 5
