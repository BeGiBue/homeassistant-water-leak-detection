"""Round 6 F05 acceptance: report intervals, accumulation and failure safety."""

from datetime import timedelta
from itertools import accumulate, cycle

import pytest
from homeassistant.core import State
from test_manager_runtime import start_manager
from test_round2_measurements import fresh, measurement_origin
from test_round5_evidence import run_sequence

from custom_components.water_leak_detection.const import DetectorKind, DetectorPhase
from custom_components.water_leak_detection.engine import DetectionEngine, DetectorSettings
from custom_components.water_leak_detection.evidence import SourceEvidence

PATTERNS = [(period,) for period in (5, 30, 60, 120, 600, 901, 1800, 3600, 86400)] + [
    (60, 120), (120, 600), (120, 901), (120, 120, 120, 120, 600),
    (120, 300, 600), (30, 60, 120, 600, 901),
]


@pytest.mark.parametrize("periods", PATTERNS)
@pytest.mark.parametrize("kind,flow", [
    (DetectorKind.SLOW_LEAK, 7), (DetectorKind.LOW_FLOW, 200),
    (DetectorKind.HIGH_FLOW, 800),
])
async def test_f05_round6_every_pattern_detects_using_only_completed_intervals(
    runtime_hass, runtime_entry, measurement_clock, periods, kind, flow
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, flow)
    manager.engine.update_settings(DetectorSettings(
        slow_detection_seconds=3600, low_detection_seconds=3600,
        high_detection_seconds=3600, high_volume_l=999999,
    ))
    confirmed = 0
    for period in cycle(periods):
        before = manager.engine.last_sample_at
        runtime = manager.engine.runtimes[kind]
        started = runtime.started_at
        measurement_clock.advance(period)
        await manager._async_tick(measurement_clock.utcnow())
        assert manager._flow_evidence.credited_seconds == 0
        assert manager.engine.last_sample_at == before
        assert runtime.started_at == started
        assert runtime.phase is DetectorPhase.MONITORING
        await fresh(runtime_hass, manager, measurement_clock, flow)
        assert manager._flow_evidence.credited_seconds == period
        confirmed += period
        assert (manager.timer_now - runtime.started_at).total_seconds() == confirmed
        if confirmed >= 3600:
            assert runtime.phase is DetectorPhase.ACTIVE
            break
        assert runtime.phase is DetectorPhase.MONITORING


def test_f05_round6_exact_thirty_hour_failure_pattern():
    periods = []
    for gap in cycle((120, 120, 120, 120, 600)):
        periods.append(gap)
        if sum(periods) >= 30 * 3600:
            break
    alarm, credits = run_sequence(periods)
    assert credits == periods
    assert alarm == next(t for t in accumulate(periods) if t >= 3600)


def test_f05_round6_exact_second_failure_sequence():
    periods = [120] * 8 + [600] + [120] * 3 + [600] + [120] * 17 + [650]
    alarm, credits = run_sequence(periods)
    assert credits == periods
    assert alarm == next(t for t in accumulate(periods) if t >= 3600)


@pytest.mark.parametrize("threshold,expected", [(3600, 3600), (90, 90), (3690, 3690)])
def test_f05_round6_additional_report_at_ninety_seconds_only_changes_observation(
    threshold, expected
):
    baseline = [120] * 40
    # Same flow and same endpoints; add a report 90 s into each 120 s interval.
    subdivided = [90, 30] * 40
    baseline_alarm, baseline_credit = run_sequence(baseline, detection_seconds=threshold)
    extra_alarm, extra_credit = run_sequence(subdivided, detection_seconds=threshold)
    assert sum(baseline_credit) == sum(extra_credit) == 4800
    assert extra_alarm == expected
    assert baseline_alarm == next(t for t in accumulate(baseline) if t >= threshold)
    assert extra_alarm >= threshold
    # Evidence at each original report remains exactly identical.
    assert list(accumulate(baseline_credit)) == list(accumulate(extra_credit))[1::2]


async def test_f05_round6_exact_single_additional_report_at_ninety_seconds(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=100, high_volume_l=99999)
    )
    measurement_clock.advance(90)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    assert manager._flow_evidence.credited_seconds == 90
    assert not manager.engine.snapshot().alarm_active
    measurement_clock.advance(30)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    assert manager._flow_evidence.credited_seconds == 30
    assert manager.engine.snapshot().alarm_active


@pytest.mark.parametrize("invalid", ["unknown", "unavailable", "-1", "bad", "nan", "inf"])
@pytest.mark.parametrize("active", [False, True])
async def test_f05_round6_failure_breaks_chain_preserves_active_and_clears_quiet(
    runtime_hass, runtime_entry, measurement_clock, invalid, active
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(DetectorSettings(
        high_detection_seconds=120, high_reset_seconds=120, high_volume_l=99999,
    ))
    measurement_clock.advance(120 if active else 30)
    await fresh(runtime_hass, manager, measurement_clock, 800)
    runtime = manager.engine.runtimes[DetectorKind.HIGH_FLOW]
    event = runtime.event_id
    if active:
        measurement_clock.advance(30)
        await fresh(runtime_hass, manager, measurement_clock, 0)
        assert runtime.quiet_since is not None
    measurement_clock.advance(10)
    await fresh(runtime_hass, manager, measurement_clock, invalid)
    assert not manager.source_available
    assert manager._flow_evidence.credited_seconds == 0
    assert runtime.quiet_since is None
    assert runtime.phase is (DetectorPhase.ACTIVE if active else DetectorPhase.MONITORING)
    measurement_clock.advance(86400)
    await manager._async_tick(measurement_clock.utcnow())
    assert runtime.event_id == event if active else runtime.event_id is None
    await fresh(runtime_hass, manager, measurement_clock, 0 if active else 800)
    assert manager._flow_evidence.credited_seconds == 0
    assert runtime.phase is (DetectorPhase.ACTIVE if active else DetectorPhase.MONITORING)
    measurement_clock.advance(30)
    await fresh(runtime_hass, manager, measurement_clock, 0 if active else 800)
    assert manager._flow_evidence.credited_seconds == 30
    assert runtime.phase is (DetectorPhase.ACTIVE if active else DetectorPhase.MONITORING)


@pytest.mark.parametrize("kind,flow", [
    (DetectorKind.SLOW_LEAK, 7), (DetectorKind.LOW_FLOW, 200),
    (DetectorKind.HIGH_FLOW, 800), (DetectorKind.BURST_LEAK, 2500),
])
async def test_f05_round6_frozen_active_quiet_timer_never_resets(
    runtime_hass, runtime_entry, measurement_clock, kind, flow
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, flow)
    manager.engine.update_settings(DetectorSettings(
        slow_detection_seconds=10, low_detection_seconds=10, high_detection_seconds=10,
    ))
    for _ in range(4):
        measurement_clock.advance(10)
        await fresh(runtime_hass, manager, measurement_clock, flow)
    runtime = manager.engine.runtimes[kind]
    assert runtime.phase is DetectorPhase.ACTIVE
    event = runtime.event_id
    measurement_clock.advance(10)
    await fresh(runtime_hass, manager, measurement_clock, 0)
    quiet = runtime.quiet_since
    assert quiet is not None
    for _ in range(4):
        measurement_clock.advance(86400)
        await manager._async_tick(measurement_clock.utcnow())
        assert manager._flow_evidence.credited_seconds == 0
        assert runtime.phase is DetectorPhase.ACTIVE
        assert runtime.event_id == event
        assert runtime.quiet_since == quiet


@pytest.mark.parametrize("with_tick", [False, True])
async def test_f05_round6_expert_max_gap_preserves_accumulated_progress(
    runtime_hass, runtime_entry, measurement_clock, with_tick
):
    manager = await start_manager(
        runtime_hass, runtime_entry, measurement_clock, 800, configured_gap=60
    )
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=120, high_volume_l=99999)
    )
    runtime = manager.engine.runtimes[DetectorKind.HIGH_FLOW]
    confirmed = 0
    for gap, credit in ((30, 30), (60, 60), (61, 0), (30, 30)):
        measurement_clock.advance(gap)
        if with_tick:
            await manager._async_tick(measurement_clock.utcnow())
            assert runtime.phase is DetectorPhase.MONITORING
        await fresh(runtime_hass, manager, measurement_clock, 800)
        assert manager._flow_evidence.credited_seconds == credit
        confirmed += credit
        assert (manager.timer_now - runtime.started_at).total_seconds() == confirmed
        assert runtime.phase is (
            DetectorPhase.ACTIVE if confirmed == 120 else DetectorPhase.MONITORING
        )


def test_f05_round6_report_history_cannot_change_later_gap_credit():
    for history in ((), (5,) * 8, (120,) * 8, (600, 901) * 10):
        evidence = SourceEvidence()
        second = 0
        evidence.observe(State("sensor.flow", "800"), second)
        for gap in history + (650,):
            second += gap
            evidence.observe(State("sensor.flow", "800"), second)
            assert evidence.credited_seconds == gap
        assert not hasattr(evidence, "candidates")


def test_f05_round6_engine_zero_credit_retains_confirmed_monitoring_time():
    engine = DetectionEngine(DetectorSettings(high_detection_seconds=120, high_volume_l=99999))
    now = measurement_origin()
    engine.sample(now, 800, None)
    engine.sample(now + timedelta(seconds=90), 800, None, evidence_seconds=90)
    engine.sample(now + timedelta(seconds=151), 800, None, evidence_seconds=0)
    runtime = engine.runtimes[DetectorKind.HIGH_FLOW]
    assert runtime.phase is DetectorPhase.MONITORING
    assert (now + timedelta(seconds=151) - runtime.started_at).total_seconds() == 90
    engine.sample(now + timedelta(seconds=181), 800, None, evidence_seconds=30)
    assert runtime.phase is DetectorPhase.ACTIVE


async def test_f05_round6_tick_cannot_admit_an_unhandled_new_report(
    runtime_hass, runtime_entry, measurement_clock
):
    from test_manager_runtime import report

    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=600, high_volume_l=99999)
    )
    # Hold the report callback: HA normally starts it eagerly in these fixtures.
    manager._unsubs.pop(0)()
    previous = manager.engine.last_sample_at
    measurement_clock.advance(600)
    report(runtime_hass, measurement_clock, 800)
    await manager._async_tick(measurement_clock.utcnow())
    assert manager._flow_evidence.credited_seconds == 0
    assert manager.engine.last_sample_at == previous
    assert not manager.engine.snapshot().alarm_active
    await manager.async_refresh()
    assert manager._flow_evidence.credited_seconds == 600
    assert manager.engine.snapshot().alarm_active


@pytest.mark.parametrize("threshold", [90, 100, 3600])
def test_f05_round6_exact_baseline_120_against_single_extra_report_90(threshold):
    baseline = [120] * 40
    additional = [90, 30] + [120] * 39
    original_alarm, original_credit = run_sequence(baseline, detection_seconds=threshold)
    additional_alarm, additional_credit = run_sequence(additional, detection_seconds=threshold)
    assert sum(original_credit) == sum(additional_credit) == 4800
    assert list(accumulate(original_credit)) == list(accumulate(additional_credit))[1:]
    assert original_alarm == next(t for t in accumulate(baseline) if t >= threshold)
    assert additional_alarm == next(t for t in accumulate(additional) if t >= threshold)
    assert additional_alarm >= threshold
