"""Tests for adaptive rolling flow learning."""

from datetime import UTC, datetime, timedelta

from custom_components.water_leak_detection.learning import (
    AdaptiveFlowLearner,
    LearningConfidence,
)


BASE = datetime(2026, 9, 1, tzinfo=UTC)


def test_safe_episode_is_admitted_after_quiet_period() -> None:
    learner = AdaptiveFlowLearner(quiet_seconds=120)
    learner.observe(BASE, 200.0, suspicious=False, high_flow_bypassed=False)
    learner.observe(
        BASE + timedelta(seconds=60),
        450.0,
        suspicious=False,
        high_flow_bypassed=False,
    )
    learner.observe(
        BASE + timedelta(seconds=120),
        0.0,
        suspicious=False,
        high_flow_bypassed=False,
    )
    changed = learner.observe(
        BASE + timedelta(seconds=240),
        0.0,
        suspicious=False,
        high_flow_bypassed=False,
    )

    assert changed is True
    snapshot = learner.snapshot(BASE + timedelta(seconds=240))
    assert snapshot.sample_count == 1
    assert snapshot.learned_max_lph == 450.0


def test_suspicious_episode_is_not_learned() -> None:
    learner = AdaptiveFlowLearner(quiet_seconds=120)
    learner.observe(BASE, 500.0, suspicious=False, high_flow_bypassed=False)
    learner.observe(
        BASE + timedelta(seconds=60),
        2500.0,
        suspicious=True,
        high_flow_bypassed=False,
    )
    learner.observe(
        BASE + timedelta(seconds=120),
        0.0,
        suspicious=False,
        high_flow_bypassed=False,
    )
    learner.observe(
        BASE + timedelta(seconds=240),
        0.0,
        suspicious=False,
        high_flow_bypassed=False,
    )

    assert learner.snapshot(BASE + timedelta(seconds=240)).sample_count == 0


def test_bypassed_high_flow_episode_is_not_learned() -> None:
    learner = AdaptiveFlowLearner(quiet_seconds=120)
    learner.observe(
        BASE,
        1200.0,
        suspicious=False,
        high_flow_bypassed=True,
    )
    learner.observe(
        BASE + timedelta(seconds=120),
        0.0,
        suspicious=False,
        high_flow_bypassed=True,
    )
    learner.observe(
        BASE + timedelta(seconds=240),
        0.0,
        suspicious=False,
        high_flow_bypassed=False,
    )

    assert learner.snapshot(BASE + timedelta(seconds=240)).sample_count == 0


def test_rolling_window_prunes_old_samples() -> None:
    learner = AdaptiveFlowLearner(window_days=14, quiet_seconds=10)

    def add_episode(start: datetime, peak: float) -> None:
        learner.observe(start, peak, suspicious=False, high_flow_bypassed=False)
        learner.observe(
            start + timedelta(seconds=10),
            0.0,
            suspicious=False,
            high_flow_bypassed=False,
        )
        learner.observe(
            start + timedelta(seconds=20),
            0.0,
            suspicious=False,
            high_flow_bypassed=False,
        )

    add_episode(BASE, 300.0)
    add_episode(BASE + timedelta(days=15), 500.0)

    snapshot = learner.snapshot(BASE + timedelta(days=15, seconds=20))
    assert snapshot.sample_count == 1
    assert snapshot.learned_max_lph == 500.0


def test_learning_adapts_to_recent_seasonal_change() -> None:
    learner = AdaptiveFlowLearner(window_days=30, quiet_seconds=10)

    def add_episode(start: datetime, peak: float) -> None:
        learner.observe(start, peak, suspicious=False, high_flow_bypassed=False)
        learner.observe(
            start + timedelta(seconds=10),
            0.0,
            suspicious=False,
            high_flow_bypassed=False,
        )
        learner.observe(
            start + timedelta(seconds=20),
            0.0,
            suspicious=False,
            high_flow_bypassed=False,
        )

    for day in range(12):
        add_episode(BASE + timedelta(days=day), 700.0)

    baseline = learner.snapshot(BASE + timedelta(days=12))
    assert baseline.learned_max_lph is not None

    for day in range(20, 28):
        add_episode(BASE + timedelta(days=day), 1200.0)

    changed = learner.snapshot(BASE + timedelta(days=28))
    assert changed.short_reference_lph is not None
    assert changed.learned_max_lph is not None
    assert changed.short_reference_lph >= 1200.0
    assert changed.learned_max_lph > baseline.learned_max_lph


def test_confidence_progresses_with_samples_and_coverage() -> None:
    learner = AdaptiveFlowLearner(window_days=30, quiet_seconds=10)

    def add_episode(start: datetime, peak: float) -> None:
        learner.observe(start, peak, suspicious=False, high_flow_bypassed=False)
        learner.observe(
            start + timedelta(seconds=10),
            0.0,
            suspicious=False,
            high_flow_bypassed=False,
        )
        learner.observe(
            start + timedelta(seconds=20),
            0.0,
            suspicious=False,
            high_flow_bypassed=False,
        )

    for idx in range(4):
        add_episode(BASE + timedelta(days=idx), 500.0 + idx)
    assert (
        learner.snapshot(BASE + timedelta(days=4)).confidence
        is LearningConfidence.INSUFFICIENT
    )

    for idx in range(4, 10):
        add_episode(BASE + timedelta(days=idx), 500.0 + idx)
    assert (
        learner.snapshot(BASE + timedelta(days=10)).confidence
        is LearningConfidence.LEARNING
    )

    for idx in range(10, 22):
        add_episode(BASE + timedelta(days=idx), 500.0 + idx)
    assert (
        learner.snapshot(BASE + timedelta(days=22)).confidence
        is LearningConfidence.RELIABLE
    )


def test_learning_round_trip_persists_only_admitted_samples() -> None:
    learner = AdaptiveFlowLearner(quiet_seconds=10)
    learner.observe(BASE, 800.0, suspicious=False, high_flow_bypassed=False)
    learner.observe(
        BASE + timedelta(seconds=10),
        0.0,
        suspicious=False,
        high_flow_bypassed=False,
    )
    learner.observe(
        BASE + timedelta(seconds=20),
        0.0,
        suspicious=False,
        high_flow_bypassed=False,
    )
    learner.observe(
        BASE + timedelta(seconds=30),
        900.0,
        suspicious=False,
        high_flow_bypassed=False,
    )

    restored = AdaptiveFlowLearner(quiet_seconds=10)
    restored.restore(learner.to_dict(), BASE + timedelta(seconds=31))

    assert restored.snapshot(BASE + timedelta(seconds=31)).sample_count == 1
