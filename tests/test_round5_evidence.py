"""F05: bounded report support, arbitrary cadence lengths and no outlier credit."""

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
    "warmup,periods",
    [((), (period,)) for period in (5, 30, 60, 120, 600, 901, 1800)]
    + [((), modes) for modes in (
        (60, 120), (120, 60), (120, 600), (600, 120), (120, 901), (901, 120),
        (120, 300, 600), (60, 120, 300, 600),
    )]
    + [((120,) * 8, (120, 901)), ((600,) * 8, (600, 120))],
)
async def test_f05_all_regular_modes_mature_without_any_tick_evidence(
    runtime_hass, runtime_entry, measurement_clock, warmup, periods
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=3600, high_volume_l=99999)
    )
    for period in warmup:
        measurement_clock.advance(period)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    credits = []
    for index in range(80):
        period = periods[index % len(periods)]
        previous = manager.engine.last_sample_at
        for part in (period / 2, period / 2):
            measurement_clock.advance(part)
            await manager._async_tick(measurement_clock.utcnow())
            assert manager.engine.last_sample_at == previous
        await fresh(runtime_hass, manager, measurement_clock, 800)
        credits.append(manager._flow_evidence.credited_seconds)
    assert all(credit > 0 for credit in credits[-20:])
    if sum(credits) >= 3600:
        assert manager.engine.runtimes[DetectorKind.HIGH_FLOW].phase is DetectorPhase.ACTIVE


def report(evidence, second):
    return evidence.observe(State("sensor.flow", "800"), second)


def test_f05_slowly_drifting_cadence_retains_recent_support():
    evidence = SourceEvidence()
    second = 0
    report(evidence, second)
    for index in range(80):
        period = 120 + index * 0.5
        second += period
        report(evidence, second)
        if index >= 3:
            assert evidence.credited_seconds == period
    assert evidence.received_at == second


def test_f05_tolerance_cannot_chain_unsupported_interval_growth():
    evidence = SourceEvidence()
    second = 0
    report(evidence, second)
    for _ in range(8):
        second += 60
        report(evidence, second)
    second += 80
    report(evidence, second)
    assert evidence.credited_seconds == 80
    second += 100
    report(evidence, second)
    assert evidence.credited_seconds == 100


@pytest.mark.parametrize("period", [86400, 604800])
def test_f05_learning_has_no_elapsed_time_cutoff(period):
    evidence = SourceEvidence()
    report(evidence, 0)
    for index in range(1, 5):
        report(evidence, index * period)
        assert evidence.credited_seconds == period


@pytest.mark.parametrize("outliers", [[600], [600, 600], [600, 650]])
def test_f05_sparse_outliers_never_obtain_support(outliers):
    automatic = SourceEvidence()
    expert = SourceEvidence()
    second = 0
    report(automatic, second)
    expert.observe(State("sensor.flow", "800"), second, configured=120)
    for outlier in outliers:
        for _ in range(17):
            second += 120
            report(automatic, second)
            expert.observe(State("sensor.flow", "800"), second, configured=120)
        second += outlier
        report(automatic, second)
        expert.observe(State("sensor.flow", "800"), second, configured=120)
        assert automatic.credited_seconds == outlier
        assert expert.credited_seconds == 0


def run_sequence(periods, *, detection_seconds=3600):
    evidence = SourceEvidence()
    engine = DetectionEngine(
        DetectorSettings(high_detection_seconds=detection_seconds, high_volume_l=99999)
    )
    second = 0
    report(evidence, second)
    engine.sample(measurement_origin(), 800, None)
    alarm_at = None
    credits = []
    for period in periods:
        second += period
        _, interrupted = report(evidence, second)
        if interrupted:
            engine.suspend_for_unavailable_source()
        engine.sample(
            measurement_origin() + timedelta(seconds=second), 800, None,
            evidence_seconds=evidence.credited_seconds,
        )
        credits.append(evidence.credited_seconds)
        if engine.snapshot().alarm_active and alarm_at is None:
            alarm_at = second
    return alarm_at, credits


def test_f05_exact_review_sequence_650_cannot_accelerate_alarm():
    periods = [120] * 8 + [600] + [120] * 3 + [600] + [120] * 17 + [650]
    alarm, credits = run_sequence(periods, detection_seconds=2400)
    assert credits == periods
    assert alarm == 2520
    baseline_alarm, _ = run_sequence([120] * 70, detection_seconds=2400)
    amended_alarm, _ = run_sequence(periods + [120] * 70, detection_seconds=2400)
    assert amended_alarm >= baseline_alarm


@pytest.mark.parametrize("seed", range(12))
def test_f05_invariant_inserting_unqualified_gaps_never_advances_alarm(seed):
    rng = random.Random(seed)
    baseline = [120] * 100
    baseline_alarm, baseline_credits = run_sequence(baseline, detection_seconds=3500)
    amended = []
    for period in baseline:
        split = rng.randrange(1, period)
        amended.extend((split, period - split))
    amended_alarm, credits = run_sequence(amended, detection_seconds=3500)
    assert sum(credits) == sum(baseline_credits) == sum(baseline)
    assert all(credit > 0 for credit in credits)
    # More observations can reveal a crossing sooner, but never before real threshold time.
    assert 3500 <= amended_alarm <= baseline_alarm


async def test_f05_unknown_unavailable_and_return_keep_profile_but_not_unknown_time(
    runtime_hass, runtime_entry, measurement_clock
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    for _ in range(8):
        measurement_clock.advance(120)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    for state in ("unknown", "unavailable"):
        measurement_clock.advance(7200)
        await fresh(runtime_hass, manager, measurement_clock, state)
        assert not manager.source_available
        measurement_clock.advance(7200)
        await fresh(runtime_hass, manager, measurement_clock, 800)
        assert manager._flow_evidence.credited_seconds == 0
        assert manager._flow_evidence.received_at == measurement_clock.seconds
        measurement_clock.advance(120)
        await fresh(runtime_hass, manager, measurement_clock, 800)
        assert manager._flow_evidence.credited_seconds == 120


@pytest.mark.parametrize("flow", [0, 800])
async def test_f05_frozen_states_and_ticks_cannot_supply_evidence(
    runtime_hass, runtime_entry, measurement_clock, flow
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, flow)
    previous = manager.engine.last_sample_at
    for _ in range(20):
        measurement_clock.advance(1800)
        await manager._async_tick(measurement_clock.utcnow())
        assert manager.engine.last_sample_at == previous
        assert not manager.engine.snapshot().alarm_active


def test_f05_explicit_expert_limit_is_independent_of_automatic_support():
    evidence = SourceEvidence()
    evidence.observe(State("sensor.flow", "800"), 0, configured=1800)
    evidence.observe(State("sensor.flow", "800"), 901, configured=1800)
    assert evidence.credited_seconds == 901
    evidence.observe(State("sensor.flow", "800"), 901 + 1801, configured=1800)
    assert evidence.credited_seconds == 0


@pytest.mark.parametrize("period", [5, 10])
def test_f05_even_fast_startup_requires_prior_qualification_before_credit(period):
    evidence = SourceEvidence()
    second = 0
    report(evidence, second)
    for _ in range(3):
        second += period
        report(evidence, second)
        assert evidence.credited_seconds == period
