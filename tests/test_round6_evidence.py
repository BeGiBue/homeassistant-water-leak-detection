"""F05: deterministic fresh-report intervals and accumulated confirmed duration."""

import random
from datetime import timedelta

import pytest
from homeassistant.core import State
from test_manager_runtime import start_manager
from test_round2_measurements import fresh, measurement_origin

from custom_components.water_leak_detection.const import DetectorKind, DetectorPhase
from custom_components.water_leak_detection.engine import DetectionEngine, DetectorSettings
from custom_components.water_leak_detection.evidence import SourceEvidence


@pytest.mark.parametrize(
    "periods",
    [(period,) for period in (5, 30, 60, 120, 600, 901, 1800, 3600, 86400)]
    + [(60, 120), (120, 600), (120, 901), (120, 120, 120, 120, 600),
       (120, 300, 600), (30, 60, 120, 300, 600)],
)
async def test_f05_every_valid_report_counts_without_cadence_learning(
    runtime_hass, runtime_entry, measurement_clock, periods
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=sum(periods) * 2, high_volume_l=999999)
    )
    accumulated = 0
    for index in range(len(periods) * 3):
        period = periods[index % len(periods)]
        previous = manager.engine.last_sample_at
        for _ in range(2):
            measurement_clock.advance(period / 2)
            await manager._async_tick(measurement_clock.utcnow())
            assert manager.engine.last_sample_at == previous
        await fresh(runtime_hass, manager, measurement_clock, 800)
        assert manager._flow_evidence.credited_seconds == period
        accumulated += period
        runtime = manager.engine.runtimes[DetectorKind.HIGH_FLOW]
        assert (manager.timer_now - runtime.started_at).total_seconds() == accumulated
    assert runtime.phase is DetectorPhase.ACTIVE


def run_intervals(periods, detection_seconds=3600, configured=0):
    source = SourceEvidence()
    engine = DetectionEngine(
        DetectorSettings(high_detection_seconds=detection_seconds, high_volume_l=999999)
    )
    origin = measurement_origin()
    now = 0
    source.observe(State("sensor.flow", "800"), now, configured)
    engine.sample(origin, 800, None, evidence_seconds=0)
    alarm = None
    progress = []
    for period in periods:
        now += period
        source.observe(State("sensor.flow", "800"), now, configured)
        engine.sample(origin + timedelta(seconds=now), 800, None,
                      evidence_seconds=source.credited_seconds)
        runtime = engine.runtimes[DetectorKind.HIGH_FLOW]
        progress.append((origin + timedelta(seconds=now) - runtime.started_at).total_seconds())
        if alarm is None and engine.snapshot().alarm_active:
            alarm = now
    return alarm, progress


def test_f05_exact_five_interval_pattern_accumulates_thirty_hours():
    periods = [120, 120, 120, 120, 600] * 100
    assert sum(periods) == 30 * 3600
    alarm, progress = run_intervals(periods, detection_seconds=7200)
    assert alarm is not None
    assert progress[-1] == 30 * 3600
    assert progress == [sum(periods[:index + 1]) for index in range(len(periods))]


def test_f05_exact_old_600_650_sequence_is_evaluated_as_actual_elapsed_reports():
    periods = [120] * 8 + [600] + [120] * 3 + [600] + [120] * 17 + [650]
    _, progress = run_intervals(periods)
    assert progress == [sum(periods[:index + 1]) for index in range(len(periods))]
    _, capped = run_intervals(periods, configured=120)
    assert capped[-1] == 28 * 120


@pytest.mark.parametrize("seed", range(12))
def test_f05_invariant_extra_true_reports_do_not_change_progress_at_original_endpoints(seed):
    rng = random.Random(seed)
    periods = [rng.choice((30, 60, 120, 600, 901)) for _ in range(40)]
    refined = []
    endpoint_indices = []
    for period in periods:
        split = rng.randrange(1, period)
        refined.extend((split, period - split))
        endpoint_indices.append(len(refined) - 1)
    _, baseline = run_intervals(periods)
    _, additional = run_intervals(refined)
    assert [additional[index] for index in endpoint_indices] == baseline


def test_f05_extra_report_after_ninety_seconds_only_observes_crossing_earlier():
    original = [120] * 30
    refined = [120] * 29 + [90, 30]
    original_alarm, original_progress = run_intervals(original, detection_seconds=3500)
    extra_alarm, extra_progress = run_intervals(refined, detection_seconds=3500)
    assert original_alarm == 3600
    assert extra_alarm == 3570  # Threshold was reached at 3500; this is a fresh observation.
    assert original_progress[-1] == extra_progress[-1] == 3600


async def test_f05_expert_limit_inclusive_sixty_preserves_previous_progress(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(
        runtime_hass, runtime_entry, measurement_clock, 800, configured_gap=60
    )
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=150, high_volume_l=999999)
    )
    for gap, credit, accumulated in ((30, 30, 30), (60, 60, 90), (61, 0, 90),
                                     (30, 30, 120), (30, 30, 150)):
        measurement_clock.advance(gap)
        await fresh(runtime_hass, manager, measurement_clock, 800)
        assert manager._flow_evidence.credited_seconds == credit
        runtime = manager.engine.runtimes[DetectorKind.HIGH_FLOW]
        assert (manager.timer_now - runtime.started_at).total_seconds() == accumulated
    assert runtime.phase is DetectorPhase.ACTIVE


@pytest.mark.parametrize("invalid", ["unknown", "unavailable", -1, "nan", "bad", "inf"])
async def test_f05_observed_invalid_source_breaks_chain_without_erasing_progress(
    runtime_hass, runtime_entry, measurement_clock, invalid
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=90, high_volume_l=999999)
    )
    measurement_clock.advance(30)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    measurement_clock.advance(10)
    await fresh(runtime_hass, manager, measurement_clock, invalid)
    assert manager._flow_evidence.credited_seconds == 0
    assert not manager.source_available
    assert not manager.engine.snapshot().alarm_active
    measurement_clock.advance(200)
    await manager._async_tick(measurement_clock.utcnow())
    await fresh(runtime_hass, manager, measurement_clock, 800)
    assert manager._flow_evidence.credited_seconds == 0
    runtime = manager.engine.runtimes[DetectorKind.HIGH_FLOW]
    assert (manager.timer_now - runtime.started_at).total_seconds() == 30
    for _ in range(2):
        measurement_clock.advance(30)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    assert runtime.phase is DetectorPhase.ACTIVE


@pytest.mark.parametrize("flow", [0, 800])
async def test_f05_frozen_high_and_null_ticks_neither_activate_nor_clear(
    runtime_hass, runtime_entry, measurement_clock, flow
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=30, high_reset_seconds=60, high_volume_l=999999)
    )
    # Before any additional report, even many ticks cannot activate.
    measurement_clock.advance(600)
    await manager._async_tick(measurement_clock.utcnow())
    assert not manager.engine.snapshot().alarm_active
    await fresh(runtime_hass, manager, measurement_clock, 800)
    event = manager.engine.snapshot().active_event_id
    assert event
    measurement_clock.advance(10)
    await fresh(runtime_hass, manager, measurement_clock, flow)
    previous = manager.engine.last_sample_at
    for _ in range(10):
        measurement_clock.advance(600)
        await manager._async_tick(measurement_clock.utcnow())
        assert manager.engine.last_sample_at == previous
        assert manager.engine.snapshot().active_event_id == event


@pytest.mark.parametrize("invalid", ["unknown", "unavailable", -1])
async def test_f05_active_leak_and_quiet_timer_survive_outage_without_quiet_credit(
    runtime_hass, runtime_entry, measurement_clock, invalid
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=30, high_reset_seconds=60, high_volume_l=999999)
    )
    measurement_clock.advance(30)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    event = manager.engine.snapshot().active_event_id
    measurement_clock.advance(10)
    await fresh(runtime_hass, manager, measurement_clock, 0)
    assert manager.engine.runtimes[DetectorKind.HIGH_FLOW].quiet_since is not None
    measurement_clock.advance(1)
    await fresh(runtime_hass, manager, measurement_clock, invalid)
    assert manager.engine.runtimes[DetectorKind.HIGH_FLOW].quiet_since is None
    measurement_clock.advance(3600)
    await manager._async_tick(measurement_clock.utcnow())
    assert manager.engine.snapshot().active_event_id == event
    await fresh(runtime_hass, manager, measurement_clock, 0)
    assert manager._flow_evidence.credited_seconds == 0
    assert manager.engine.snapshot().active_event_id == event
    measurement_clock.advance(59)
    await fresh(runtime_hass, manager, measurement_clock, 0)
    assert manager.engine.snapshot().active_event_id == event
    measurement_clock.advance(1)
    await fresh(runtime_hass, manager, measurement_clock, 0)
    assert not manager.engine.snapshot().alarm_active
