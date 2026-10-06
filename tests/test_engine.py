"""Tests for detector state machines."""

from datetime import UTC, datetime, timedelta

from custom_components.water_leak_detection.const import DetectorKind, DetectorPhase
from custom_components.water_leak_detection.engine import DetectionEngine, DetectorSettings


def at(seconds: int) -> datetime:
    return datetime(2026, 10, 6, tzinfo=UTC) + timedelta(seconds=seconds)


def test_slow_leak_detects_seven_lph_after_hour() -> None:
    engine = DetectionEngine()
    engine.sample(at(0), 7.0, 1000.0)
    assert engine.runtimes[DetectorKind.SLOW_LEAK].phase is DetectorPhase.MONITORING
    engine.sample(at(3599), 7.0, 1006.9)
    assert engine.runtimes[DetectorKind.SLOW_LEAK].phase is DetectorPhase.MONITORING
    engine.sample(at(3600), 7.0, 1007.0)
    assert engine.runtimes[DetectorKind.SLOW_LEAK].phase is DetectorPhase.ACTIVE


def test_slow_monitoring_requires_continuous_flow() -> None:
    engine = DetectionEngine()
    engine.sample(at(0), 7.0, None)
    engine.sample(at(1800), 0.0, None)
    assert engine.runtimes[DetectorKind.SLOW_LEAK].phase is DetectorPhase.IDLE


def test_low_flow_short_pause_does_not_reset() -> None:
    engine = DetectionEngine()
    engine.sample(at(0), 200.0, None)
    engine.sample(at(3000), 0.0, None)
    engine.sample(at(3300), 200.0, None)
    engine.sample(at(3600), 200.0, None)
    assert engine.runtimes[DetectorKind.LOW_FLOW].phase is DetectorPhase.ACTIVE


def test_low_flow_seven_minute_quiet_period_resets() -> None:
    engine = DetectionEngine()
    engine.sample(at(0), 200.0, None)
    engine.sample(at(3000), 0.0, None)
    engine.sample(at(3420), 0.0, None)
    assert engine.runtimes[DetectorKind.LOW_FLOW].phase is DetectorPhase.IDLE


def test_high_flow_bypass_only_resets_high_flow() -> None:
    settings = DetectorSettings(
        high_detection_seconds=10,
        burst_threshold_lph=1000,
        burst_detection_seconds=10,
    )
    engine = DetectionEngine(settings)
    engine.sample(at(0), 2500.0, None)
    engine.sample(at(10), 2500.0, None, high_flow_bypassed=True)
    assert engine.runtimes[DetectorKind.HIGH_FLOW].phase is DetectorPhase.IDLE
    assert engine.runtimes[DetectorKind.BURST_LEAK].phase is DetectorPhase.ACTIVE


def test_shutdown_mapping_is_independent() -> None:
    settings = DetectorSettings(
        slow_detection_seconds=1,
        shutoff_slow=True,
        shutoff_burst=False,
    )
    engine = DetectionEngine(settings)
    engine.sample(at(0), 10.0, None)
    engine.sample(at(1), 10.0, None)
    snapshot = engine.snapshot()
    assert snapshot.alarm_active is True
    assert snapshot.shutoff_request is True


def test_engine_runtime_round_trip() -> None:
    settings = DetectorSettings(slow_detection_seconds=1)
    engine = DetectionEngine(settings)
    engine.sample(at(0), 10.0, 1000.0)
    engine.sample(at(1), 10.0, 1000.1)
    event_id = engine.runtimes[DetectorKind.SLOW_LEAK].event_id

    restored = DetectionEngine(settings)
    restored.restore(engine.to_dict())
    assert restored.runtimes[DetectorKind.SLOW_LEAK].phase is DetectorPhase.ACTIVE
    assert restored.runtimes[DetectorKind.SLOW_LEAK].event_id == event_id
