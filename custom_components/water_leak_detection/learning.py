"""Rolling adaptive learning for normal household water flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from math import isfinite
from typing import Any


class LearningConfidence(StrEnum):
    """Confidence state for the adaptive model."""

    INSUFFICIENT = "insufficient"
    LEARNING = "learning"
    RELIABLE = "reliable"


@dataclass(slots=True, frozen=True)
class LearningSample:
    """One completed, non-suspicious water-use episode."""

    timestamp: datetime
    peak_lph: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "peak_lph": self.peak_lph,
        }


@dataclass(slots=True, frozen=True)
class LearningSnapshot:
    """Current rolling learning result."""

    learned_max_lph: float | None
    short_reference_lph: float | None
    long_reference_lph: float | None
    sample_count: int
    coverage_days: int
    age_days: int
    window_days: int
    confidence: LearningConfidence


@dataclass(slots=True)
class _Episode:
    """In-progress water-use episode; never persisted as normal evidence."""

    started_at: datetime
    peak_lph: float
    excluded: bool = False
    quiet_since: datetime | None = None


class AdaptiveFlowLearner:
    """Learn a robust rolling normal peak from completed safe episodes."""

    def __init__(
        self,
        *,
        window_days: int = 30,
        quiet_flow_lph: float = 1.0,
        quiet_seconds: float = 120.0,
    ) -> None:
        self.window_days = max(7, int(window_days))
        self.quiet_flow_lph = max(0.0, float(quiet_flow_lph))
        self.quiet_seconds = max(10.0, float(quiet_seconds))
        self.samples: list[LearningSample] = []
        self._episode: _Episode | None = None

    def update_window(self, window_days: int, now: datetime) -> None:
        """Change the rolling window while retaining still-valid samples."""
        self.window_days = max(7, int(window_days))
        self._prune(now)

    def observe(
        self,
        now: datetime,
        flow_lph: float,
        *,
        runtime_now: datetime | None = None,
        suspicious: bool,
        high_flow_bypassed: bool,
    ) -> bool:
        """Observe a flow sample.

        Returns True when the learned sample set changed.
        """
        timing = now if runtime_now is None else runtime_now
        flow = max(0.0, float(flow_lph))
        changed = self._prune(now)

        if self._episode is None:
            if flow >= self.quiet_flow_lph:
                self._episode = _Episode(
                    started_at=timing,
                    peak_lph=flow,
                    excluded=suspicious or high_flow_bypassed,
                )
            return changed

        episode = self._episode
        episode.peak_lph = max(episode.peak_lph, flow)
        if suspicious or high_flow_bypassed:
            episode.excluded = True

        if flow < self.quiet_flow_lph:
            episode.quiet_since = episode.quiet_since or timing
            quiet_elapsed = (timing - episode.quiet_since).total_seconds()
            if quiet_elapsed >= self.quiet_seconds:
                if not episode.excluded and episode.peak_lph > 0:
                    self.samples.append(
                        LearningSample(timestamp=now, peak_lph=episode.peak_lph)
                    )
                    changed = True
                self._episode = None
        else:
            episode.quiet_since = None

        return changed

    def suspend_current_episode(self) -> None:
        """Discard an incomplete episode after source unavailability/restart."""
        self._episode = None

    def reset(self) -> None:
        """Clear all learned history."""
        self.samples.clear()
        self._episode = None

    def snapshot(self, now: datetime) -> LearningSnapshot:
        """Return robust short/long references and confidence."""
        self._prune(now)
        peaks = [sample.peak_lph for sample in self.samples]
        short_cutoff = now - timedelta(days=min(7, self.window_days))
        short_peaks = [
            sample.peak_lph
            for sample in self.samples
            if sample.timestamp >= short_cutoff
        ]

        long_ref = _percentile(peaks, 0.95)
        short_ref = _percentile(short_peaks, 0.95)

        learned: float | None
        if long_ref is None:
            learned = None
        elif short_ref is None:
            learned = long_ref
        else:
            # Short-term behavior gets more weight for seasonal adaptation while
            # the long-term reference prevents abrupt drops.
            weighted = (0.65 * short_ref) + (0.35 * long_ref)
            learned = max(weighted, long_ref * 0.85)

        coverage_dates = {sample.timestamp.date() for sample in self.samples}
        coverage_days = len(coverage_dates)
        age_days = 0
        if self.samples:
            age_days = max(
                1,
                int(
                    (
                        now - min(sample.timestamp for sample in self.samples)
                    ).total_seconds()
                    // 86400
                )
                + 1,
            )

        sample_count = len(self.samples)
        reliable_days = min(14, max(7, self.window_days // 2))
        if sample_count < 5 or coverage_days < 3:
            confidence = LearningConfidence.INSUFFICIENT
        elif sample_count < 20 or coverage_days < reliable_days:
            confidence = LearningConfidence.LEARNING
        else:
            confidence = LearningConfidence.RELIABLE

        return LearningSnapshot(
            learned_max_lph=learned,
            short_reference_lph=short_ref,
            long_reference_lph=long_ref,
            sample_count=sample_count,
            coverage_days=coverage_days,
            age_days=age_days,
            window_days=self.window_days,
            confidence=confidence,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize only admitted normal samples.

        The in-progress episode is intentionally not persisted because an
        incomplete pre-restart episode is not trustworthy learning evidence.
        """
        return {
            "samples": [sample.to_dict() for sample in self.samples],
        }

    def restore(self, raw: Any, now: datetime) -> None:
        """Restore valid admitted samples."""
        if not isinstance(raw, dict):
            return
        samples = raw.get("samples")
        if not isinstance(samples, list):
            return

        restored: list[LearningSample] = []
        for item in samples:
            if not isinstance(item, dict):
                continue
            timestamp_raw = item.get("timestamp")
            peak_raw = item.get("peak_lph")
            if not isinstance(timestamp_raw, str):
                continue
            try:
                timestamp = datetime.fromisoformat(timestamp_raw)
                peak = float(peak_raw)
            except (TypeError, ValueError):
                continue
            if timestamp.tzinfo is not None and timestamp <= now and isfinite(peak) and peak > 0:
                restored.append(LearningSample(timestamp=timestamp, peak_lph=peak))
        self.samples = restored
        self._episode = None
        self._prune(now)

    def _prune(self, now: datetime) -> bool:
        cutoff = now - timedelta(days=self.window_days)
        before = len(self.samples)
        self.samples = [sample for sample in self.samples if sample.timestamp >= cutoff]
        return len(self.samples) != before


def _percentile(values: list[float], quantile: float) -> float | None:
    """Return a linearly interpolated percentile without external dependencies."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
