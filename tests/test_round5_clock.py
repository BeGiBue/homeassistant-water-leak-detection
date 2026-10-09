"""F15: exact admitted sample identities, small rollbacks and bounded lifecycle."""

from copy import deepcopy
from datetime import timedelta

import pytest
from test_manager_runtime import start_manager
from test_round2_measurements import fresh, measurement_origin

from custom_components.water_leak_detection.const import DOMAIN
from custom_components.water_leak_detection.learning import AdaptiveFlowLearner, LearningSample
from custom_components.water_leak_detection.manager import WaterLeakManager


def clock_store(shifts=(-3600,), count=1):
    noon = measurement_origin().replace(hour=12)
    learner = AdaptiveFlowLearner(quiet_seconds=10)
    for index in range(count):
        end = noon - timedelta(seconds=(count - index - 1) * 30)
        for delta, flow in ((-11, 50 + index), (-10, 0), (0, 0)):
            now = end + timedelta(seconds=delta)
            learner.observe(now, flow, runtime_now=now, suspicious=False, high_flow_bypassed=False)
    assert len(learner.samples) == count
    wall = noon
    for shift in shifts:
        wall += timedelta(seconds=shift)
        raw = learner.to_dict(now=wall, runtime_now=noon)
    return learner, raw, wall, noon


@pytest.mark.parametrize("shift", [-0.5, -3600, -7200, 3600])
async def test_f15_sample_then_clock_shift_real_unload_and_three_restarts(
    runtime_hass, runtime_entry, measurement_clock, shift
):
    manager = await start_manager(runtime_hass, runtime_entry, measurement_clock, 50)
    for _ in range(25):
        measurement_clock.advance(5)
        await fresh(runtime_hass, manager, measurement_clock, 0)
    original = list(manager.learner.samples)
    assert len(original) == 1
    measurement_clock.wall_shift += shift
    for _ in range(3):
        await manager.async_unload()
        manager = WaterLeakManager(runtime_hass, runtime_entry)
        runtime_hass.data[DOMAIN][runtime_entry.entry_id] = manager
        await manager.async_setup()
        assert manager.learner.samples == original


@pytest.mark.parametrize(
    "mutation",
    ["within_range", "extreme", "same_time_new_value", "same_value_new_time", "arbitrary_future"],
)
def test_f15_exact_review_injected_1130_sample_never_inherits_noon_permission(mutation):
    learner, raw, wall, noon = clock_store()
    original = learner.samples[0]
    if mutation == "same_time_new_value":
        injected = LearningSample(noon, original.peak_lph + 1)
    elif mutation == "same_value_new_time":
        injected = LearningSample(noon - timedelta(minutes=1), original.peak_lph)
    elif mutation == "arbitrary_future":
        injected = LearningSample(noon + timedelta(days=3650), 50)
    else:
        injected = LearningSample(
            noon - timedelta(minutes=30), 50000 if mutation == "extreme" else 75
        )
    assert wall.hour == 11 and noon.hour == 12
    raw["samples"].append(injected.to_dict())
    restored = AdaptiveFlowLearner()
    restored.restore(raw, wall)
    assert restored.samples == [original]


@pytest.mark.parametrize("field", ["timestamp", "peak_lph"])
def test_f15_modified_admitted_sample_itself_is_rejected(field):
    _, raw, wall, noon = clock_store()
    raw["samples"][0][field] = (
        (noon - timedelta(minutes=30)).isoformat() if field == "timestamp" else 50000
    )
    restored = AdaptiveFlowLearner()
    restored.restore(raw, wall)
    assert not restored.samples


@pytest.mark.parametrize(
    "damage",
    [None, {}, {"fingerprints": []}, {"fingerprints": ["bad"]},
     {"fingerprints": None}, {"observed_at": "bad"}, {"valid_until": "bad"}],
)
def test_f15_missing_or_corrupt_context_never_opens_time_range(damage):
    _, raw, wall, _ = clock_store()
    if damage is None:
        raw.pop("clock_rollback")
    elif not damage:
        raw["clock_rollback"] = {}
    else:
        raw["clock_rollback"].update(damage)
    restored = AdaptiveFlowLearner()
    restored.restore(raw, wall)
    assert not restored.samples


def test_f15_multiple_rollbacks_multiple_admitted_samples_and_new_episode():
    learner, raw, wall, noon = clock_store((-3600, 1800, -5400), count=3)
    originals = list(learner.samples)
    assert len(raw["clock_rollback"]["fingerprints"]) == 3
    restored = AdaptiveFlowLearner(quiet_seconds=10)
    restored.restore(raw, wall)
    for delta, flow in ((1, 80), (2, 0), (12, 0)):
        restored.observe(
            wall + timedelta(seconds=delta), flow, runtime_now=noon + timedelta(seconds=delta),
            suspicious=False, high_flow_bypassed=False,
        )
    expected = originals + [LearningSample(wall + timedelta(seconds=12), 80)]
    assert restored.samples == expected
    raw = restored.to_dict(
        now=wall + timedelta(seconds=12), runtime_now=noon + timedelta(seconds=12)
    )
    assert len(raw["clock_rollback"]["fingerprints"]) == 3
    restored_again = AdaptiveFlowLearner()
    restored_again.restore(raw, wall + timedelta(seconds=12))
    assert restored_again.samples == expected
    # A second observed rollback must authorize the newly completed sample too.
    restored_again.observe_clock(wall + timedelta(seconds=12), noon)
    raw = restored_again.to_dict(now=wall - timedelta(hours=1), runtime_now=noon)
    assert len(raw["clock_rollback"]["fingerprints"]) == 4


def test_f15_context_is_removed_when_utc_catches_up_and_history_prunes():
    learner, raw, wall, noon = clock_store(count=3)
    restored = AdaptiveFlowLearner()
    restored.restore(raw, wall)
    original = list(restored.samples)
    for _ in range(3):
        raw = restored.to_dict(now=wall, runtime_now=wall)
        restored = AdaptiveFlowLearner()
        restored.restore(raw, wall)
        assert restored.samples == original
        assert len(raw["clock_rollback"]["fingerprints"]) == 3
    raw = restored.to_dict(now=noon, runtime_now=wall)
    assert "clock_rollback" not in raw
    assert not restored._rollback_samples
    assert restored.snapshot(noon + timedelta(days=29)).sample_count == 3
    assert restored.snapshot(noon + timedelta(days=31)).sample_count == 0
    assert not restored._rollback_samples
    assert learner.samples == original


def test_f15_offline_rollback_does_not_reuse_context_for_an_unobserved_epoch():
    _, raw, wall, _ = clock_store()
    restored = AdaptiveFlowLearner()
    restored.restore(raw, wall - timedelta(seconds=0.5))
    assert not restored.samples


def test_f15_duplicate_injected_future_records_cannot_increase_admitted_count():
    learner, raw, wall, _ = clock_store(count=3)
    raw["samples"].extend([dict(raw["samples"][0]) for _ in range(10)])
    restored = AdaptiveFlowLearner()
    restored.restore(raw, wall)
    assert restored.samples == learner.samples


def test_f15_submillisecond_read_jitter_does_not_create_permission():
    learner, _, wall, noon = clock_store((0,))
    raw = learner.to_dict(now=wall - timedelta(microseconds=100), runtime_now=noon)
    assert "clock_rollback" not in raw


@pytest.mark.parametrize("shift", [-0.5, -3600, -7200, 3600])
def test_f15_invariant_clock_context_authorizes_only_previously_admitted_samples(shift):
    learner, raw, wall, noon = clock_store((shift,), count=3)
    admitted = list(learner.samples)
    for index in range(10):
        raw["samples"].append(LearningSample(
            max(wall, noon) + timedelta(microseconds=index + 1), 50000 + index
        ).to_dict())
    restored = AdaptiveFlowLearner()
    restored.restore(deepcopy(raw), wall)
    assert restored.samples == admitted
