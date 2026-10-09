"""F05: independently maturing report modes without retrospective evidence."""

import pytest
from homeassistant.core import State
from test_manager_runtime import start_manager
from test_round2_measurements import fresh

from custom_components.water_leak_detection.const import DetectorKind, DetectorPhase
from custom_components.water_leak_detection.engine import DetectorSettings
from custom_components.water_leak_detection.evidence import SourceEvidence


@pytest.mark.parametrize(
    "warmup,periods",
    [
        (0, (120, 600)), (0, (600, 120)),
        (8, (120, 600)), (8, (600, 120)),
        (0, (60, 120)), (0, (120, 60)),
    ],
)
async def test_f05_alternating_modes_mature_for_six_hours_with_no_tick_credit(
    runtime_hass, runtime_entry, measurement_clock, warmup, periods
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 800)
    manager.engine.update_settings(
        DetectorSettings(high_detection_seconds=3600, high_volume_l=99999)
    )
    for _ in range(warmup):
        measurement_clock.advance(120)
        await fresh(runtime_hass, manager, measurement_clock, 800)
    start = measurement_clock.seconds
    credited = 0
    index = 0
    while measurement_clock.seconds - start < 6 * 3600:
        period = periods[index % len(periods)]
        index += 1
        before = manager.engine.last_sample_at
        for _ in range(period // 30):
            measurement_clock.advance(30)
            await manager._async_tick(measurement_clock.utcnow())
            assert manager.engine.last_sample_at == before
        await fresh(runtime_hass, manager, measurement_clock, 800)
        credit = manager._flow_evidence.credited_seconds
        assert credit == period
        credited += credit
    assert credited >= 4 * 3600
    assert manager.engine.runtimes[DetectorKind.HIGH_FLOW].phase is DetectorPhase.ACTIVE


def observe(evidence, second):
    return evidence.observe(State("sensor.flow", "800"), second)


def test_f05_single_long_outlier_retains_short_mode_without_qualifying_long_mode():
    evidence = SourceEvidence()
    second = 0
    observe(evidence, second)
    for gap in [120] * 8 + [600] + [120] * 8 + [600]:
        second += gap
        assert observe(evidence, second) == (True, False)
        assert evidence.credited_seconds == gap
    assert evidence.received_at == second


def test_f05_qualification_only_credits_future_intervals_and_outages_keep_profile():
    evidence = SourceEvidence()
    second = 0
    observe(evidence, second)
    for gap in [120] * 8 + [600, 120] * 8:
        second += gap
        observe(evidence, second)
        assert evidence.credited_seconds == gap
    # An explicitly observed source interruption breaks the chain, not a learned mode.
    evidence.invalidate()
    second += 7200
    assert observe(evidence, second) == (True, False)
    assert evidence.credited_seconds == 0
    for _ in range(3):
        second += 120
        observe(evidence, second)
        assert evidence.credited_seconds == 120


def test_f05_explicit_gap_keeps_existing_outage_boundary():
    evidence = SourceEvidence()
    evidence.observe(State("sensor.flow", "800"), 0, configured=120)
    assert evidence.observe(State("sensor.flow", "800"), 600, configured=120) == (True, True)
    assert evidence.credited_seconds == 0
    evidence.observe(State("sensor.flow", "800"), 720, configured=120)
    assert evidence.credited_seconds == 120
