"""Pure detection engine for water leak detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from .const import DETECTOR_PRIORITY, DetectorKind, DetectorPhase


@dataclass(slots=True)
class DetectorSettings:
    """Detector thresholds and timing."""

    slow_enabled: bool = True
    slow_threshold_lph: float = 3.0
    slow_detection_seconds: float = 3600.0
    slow_reset_seconds: float = 600.0
    low_enabled: bool = True
    low_threshold_lph: float = 150.0
    low_detection_seconds: float = 3600.0
    low_quiet_lph: float = 20.0
    low_reset_seconds: float = 420.0
    high_threshold_lph: float = 600.0
    high_detection_seconds: float = 2700.0
    high_volume_l: float = 500.0
    high_quiet_lph: float = 100.0
    high_reset_seconds: float = 300.0
    burst_threshold_lph: float = 2000.0
    burst_detection_seconds: float = 30.0
    burst_reset_lph: float = 500.0
    burst_reset_seconds: float = 60.0
    burst_rate_rise_lph_10s: float = 1000.0
    burst_rate_confirm_seconds: float = 10.0
    shutoff_slow: bool = False
    shutoff_low: bool = False
    shutoff_high: bool = False
    shutoff_burst: bool = True


@dataclass(slots=True)
class DetectorRuntime:
    """Mutable state for one detector."""

    phase: DetectorPhase = DetectorPhase.IDLE
    started_at: datetime | None = None
    detected_at: datetime | None = None
    quiet_since: datetime | None = None
    event_id: str | None = None
    start_total_l: float | None = None
    estimated_volume_l: float = 0.0
    reason: str | None = None

    def reset(self) -> None:
        """Reset detector runtime."""
        self.phase = DetectorPhase.IDLE
        self.started_at = None
        self.detected_at = None
        self.quiet_since = None
        self.event_id = None
        self.start_total_l = None
        self.estimated_volume_l = 0.0
        self.reason = None


@dataclass(slots=True, frozen=True)
class DetectorTransition:
    """One detector phase transition."""

    kind: DetectorKind
    old_phase: DetectorPhase
    new_phase: DetectorPhase
    event_id: str | None
    started_at: datetime | None
    detected_at: datetime | None
    volume_l: float


@dataclass(slots=True)
class EngineSnapshot:
    """Current high-level engine state."""

    status: str
    alarm_active: bool
    shutoff_request: bool
    active_kind: DetectorKind | None
    active_event_id: str | None
    active_started_at: datetime | None
    active_detected_at: datetime | None
    active_volume_l: float


@dataclass(slots=True)
class DetectionEngine:
    """State machine for Slow, Low, High and Burst water events."""

    settings: DetectorSettings = field(default_factory=DetectorSettings)
    runtimes: dict[DetectorKind, DetectorRuntime] = field(
        default_factory=lambda: {kind: DetectorRuntime() for kind in DetectorKind}
    )
    last_sample_at: datetime | None = None
    last_flow_lph: float | None = None

    def update_settings(self, settings: DetectorSettings) -> None:
        """Apply updated thresholds without discarding current state."""
        self.settings = settings

    def suspend_for_unavailable_source(self) -> None:
        """Suspend evidence timers while the source measurement is unavailable.

        Unconfirmed monitoring must not accumulate unknown time. Confirmed events
        remain active for safety, but any in-progress quiet/reset interval is
        cleared because an unavailable source is not evidence of zero flow.
        """
        for runtime in self.runtimes.values():
            runtime.quiet_since = None
            if runtime.phase is DetectorPhase.MONITORING:
                runtime.reset()
        self.last_sample_at = None
        self.last_flow_lph = None

    def sample(
        self,
        now: datetime,
        flow_lph: float,
        total_l: float | None,
        *,
        high_flow_bypassed: bool = False,
        effective_high_threshold_lph: float | None = None,
        effective_burst_threshold_lph: float | None = None,
    ) -> list[DetectorTransition]:
        """Evaluate one measurement sample."""
        if flow_lph < 0:
            flow_lph = 0.0

        delta_seconds = 0.0
        if self.last_sample_at is not None:
            delta_seconds = max(0.0, (now - self.last_sample_at).total_seconds())
            # Avoid integrating an arbitrarily large gap after HA was offline.
            delta_seconds = min(delta_seconds, 300.0)

        if delta_seconds > 0:
            for runtime in self.runtimes.values():
                if runtime.phase is not DetectorPhase.IDLE:
                    runtime.estimated_volume_l += flow_lph * delta_seconds / 3600.0

        effective_high = (
            self.settings.high_threshold_lph
            if effective_high_threshold_lph is None
            else max(self.settings.low_threshold_lph, float(effective_high_threshold_lph))
        )
        effective_burst = (
            self.settings.burst_threshold_lph
            if effective_burst_threshold_lph is None
            else max(effective_high, float(effective_burst_threshold_lph))
        )

        previous_flow = self.last_flow_lph
        previous_at = self.last_sample_at

        transitions: list[DetectorTransition] = []

        if self.settings.slow_enabled:
            transitions.extend(self._sample_slow(now, flow_lph, total_l))
        elif self.runtimes[DetectorKind.SLOW_LEAK].phase is not DetectorPhase.IDLE:
            self._append_transition(
                transitions,
                DetectorKind.SLOW_LEAK,
                DetectorPhase.IDLE,
                now=now,
                total_l=total_l,
            )

        if self.settings.low_enabled:
            transitions.extend(
                self._sample_low(now, flow_lph, total_l, effective_high)
            )
        elif self.runtimes[DetectorKind.LOW_FLOW].phase is not DetectorPhase.IDLE:
            self._append_transition(
                transitions,
                DetectorKind.LOW_FLOW,
                DetectorPhase.IDLE,
                now=now,
                total_l=total_l,
            )
        transitions.extend(
            self._sample_high(
                now,
                flow_lph,
                total_l,
                high_flow_bypassed,
                effective_high,
            )
        )
        transitions.extend(
            self._sample_burst(
                now,
                flow_lph,
                total_l,
                effective_burst,
                effective_high,
                previous_flow,
                previous_at,
            )
        )

        self.last_sample_at = now
        self.last_flow_lph = flow_lph
        return transitions

    def _transition(
        self,
        kind: DetectorKind,
        new_phase: DetectorPhase,
        *,
        now: datetime,
        total_l: float | None,
    ) -> DetectorTransition | None:
        runtime = self.runtimes[kind]
        old_phase = runtime.phase
        if old_phase is new_phase:
            return None

        if new_phase is DetectorPhase.MONITORING:
            runtime.phase = new_phase
            runtime.started_at = now
            runtime.detected_at = None
            runtime.quiet_since = None
            runtime.event_id = None
            runtime.start_total_l = total_l
            runtime.estimated_volume_l = 0.0
        elif new_phase is DetectorPhase.ACTIVE:
            runtime.phase = new_phase
            runtime.detected_at = now
            runtime.quiet_since = None
            runtime.event_id = self._new_event_id(kind, now)
        else:
            transition = DetectorTransition(
                kind=kind,
                old_phase=old_phase,
                new_phase=new_phase,
                event_id=runtime.event_id,
                started_at=runtime.started_at,
                detected_at=runtime.detected_at,
                volume_l=self._event_volume(runtime, total_l),
            )
            runtime.reset()
            return transition

        return DetectorTransition(
            kind=kind,
            old_phase=old_phase,
            new_phase=new_phase,
            event_id=runtime.event_id,
            started_at=runtime.started_at,
            detected_at=runtime.detected_at,
            volume_l=self._event_volume(runtime, total_l),
        )

    def _append_transition(
        self,
        out: list[DetectorTransition],
        kind: DetectorKind,
        new_phase: DetectorPhase,
        *,
        now: datetime,
        total_l: float | None,
    ) -> bool:
        """Append a transition when one occurred."""
        transition = self._transition(
            kind, new_phase, now=now, total_l=total_l
        )
        if transition is None:
            return False
        out.append(transition)
        return True

    @staticmethod
    def _new_event_id(kind: DetectorKind, now: datetime) -> str:
        return f"{kind.value}_{now.strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:6]}"

    @staticmethod
    def _elapsed(now: datetime, start: datetime | None) -> float:
        if start is None:
            return 0.0
        return max(0.0, (now - start).total_seconds())

    def _event_volume(self, runtime: DetectorRuntime, total_l: float | None) -> float:
        if total_l is not None and runtime.start_total_l is not None:
            delta = total_l - runtime.start_total_l
            if delta >= 0:
                return delta
        return runtime.estimated_volume_l

    def _sample_slow(
        self, now: datetime, flow: float, total_l: float | None
    ) -> list[DetectorTransition]:
        kind = DetectorKind.SLOW_LEAK
        runtime = self.runtimes[kind]
        s = self.settings
        out: list[DetectorTransition] = []

        if runtime.phase is DetectorPhase.IDLE:
            if s.slow_threshold_lph <= flow < s.low_threshold_lph:
                self._append_transition(
                    out,
                    kind,
                    DetectorPhase.MONITORING,
                    now=now,
                    total_l=total_l,
                )
            return out

        if runtime.phase is DetectorPhase.MONITORING:
            # Slow leak intentionally requires continuous low-band flow. A normal
            # larger draw interrupts the evidence window but does not clear an
            # already confirmed Slow Leak.
            if flow < s.slow_threshold_lph or flow >= s.low_threshold_lph:
                self._append_transition(
                    out,
                    kind,
                    DetectorPhase.IDLE,
                    now=now,
                    total_l=total_l,
                )
            elif self._elapsed(now, runtime.started_at) >= s.slow_detection_seconds:
                self._append_transition(
                    out,
                    kind,
                    DetectorPhase.ACTIVE,
                    now=now,
                    total_l=total_l,
                )
            return out

        if flow < s.slow_threshold_lph:
            runtime.quiet_since = runtime.quiet_since or now
            if self._elapsed(now, runtime.quiet_since) >= s.slow_reset_seconds:
                self._append_transition(
                    out,
                    kind,
                    DetectorPhase.IDLE,
                    now=now,
                    total_l=total_l,
                )
        else:
            runtime.quiet_since = None
        return out

    def _sample_low(
        self,
        now: datetime,
        flow: float,
        total_l: float | None,
        high_threshold_lph: float,
    ) -> list[DetectorTransition]:
        kind = DetectorKind.LOW_FLOW
        runtime = self.runtimes[kind]
        s = self.settings
        out: list[DetectorTransition] = []

        if runtime.phase is DetectorPhase.IDLE:
            if s.low_threshold_lph <= flow < high_threshold_lph:
                self._append_transition(
                    out,
                    kind,
                    DetectorPhase.MONITORING,
                    now=now,
                    total_l=total_l,
                )
            return out

        if (
            runtime.phase is DetectorPhase.MONITORING
            and flow >= high_threshold_lph
        ):
            self._append_transition(
                out,
                kind,
                DetectorPhase.IDLE,
                now=now,
                total_l=total_l,
            )
            return out

        if flow < s.low_quiet_lph:
            runtime.quiet_since = runtime.quiet_since or now
            if self._elapsed(now, runtime.quiet_since) >= s.low_reset_seconds:
                self._append_transition(
                    out,
                    kind,
                    DetectorPhase.IDLE,
                    now=now,
                    total_l=total_l,
                )
                return out
        else:
            runtime.quiet_since = None

        if (
            runtime.phase is DetectorPhase.MONITORING
            and self._elapsed(now, runtime.started_at) >= s.low_detection_seconds
        ):
            self._append_transition(
                out,
                kind,
                DetectorPhase.ACTIVE,
                now=now,
                total_l=total_l,
            )
        return out

    def _sample_high(
        self,
        now: datetime,
        flow: float,
        total_l: float | None,
        bypassed: bool,
        high_threshold_lph: float,
    ) -> list[DetectorTransition]:
        kind = DetectorKind.HIGH_FLOW
        runtime = self.runtimes[kind]
        s = self.settings
        out: list[DetectorTransition] = []

        if bypassed:
            if runtime.phase is not DetectorPhase.IDLE:
                self._append_transition(
                    out,
                    kind,
                    DetectorPhase.IDLE,
                    now=now,
                    total_l=total_l,
                )
            return out

        if runtime.phase is DetectorPhase.IDLE:
            if s.high_threshold_lph <= flow < s.burst_threshold_lph:
                self._append_transition(
                    out,
                    kind,
                    DetectorPhase.MONITORING,
                    now=now,
                    total_l=total_l,
                )
            return out

        if flow < s.high_quiet_lph:
            runtime.quiet_since = runtime.quiet_since or now
            if self._elapsed(now, runtime.quiet_since) >= s.high_reset_seconds:
                self._append_transition(
                    out,
                    kind,
                    DetectorPhase.IDLE,
                    now=now,
                    total_l=total_l,
                )
                return out
        else:
            runtime.quiet_since = None

        if runtime.phase is DetectorPhase.MONITORING:
            volume = self._event_volume(runtime, total_l)
            if (
                self._elapsed(now, runtime.started_at) >= s.high_detection_seconds
                or volume >= s.high_volume_l
            ):
                self._append_transition(
                    out,
                    kind,
                    DetectorPhase.ACTIVE,
                    now=now,
                    total_l=total_l,
                )
        return out

    def _sample_burst(
        self,
        now: datetime,
        flow: float,
        total_l: float | None,
        burst_threshold_lph: float,
        high_threshold_lph: float,
        previous_flow: float | None,
        previous_at: datetime | None,
    ) -> list[DetectorTransition]:
        kind = DetectorKind.BURST_LEAK
        runtime = self.runtimes[kind]
        s = self.settings
        out: list[DetectorTransition] = []

        rise_lph_10s = 0.0
        if previous_flow is not None and previous_at is not None:
            elapsed = (now - previous_at).total_seconds()
            if 0 < elapsed <= 60:
                rise_lph_10s = max(0.0, flow - previous_flow) * 10.0 / elapsed

        dynamic_floor = max(high_threshold_lph * 1.8, burst_threshold_lph * 0.75)
        dynamic_candidate = (
            rise_lph_10s >= s.burst_rate_rise_lph_10s
            and flow >= dynamic_floor
        )
        absolute_candidate = flow >= burst_threshold_lph

        if runtime.phase is DetectorPhase.IDLE:
            if absolute_candidate or dynamic_candidate:
                if self._append_transition(
                    out, kind, DetectorPhase.MONITORING, now=now, total_l=total_l
                ):
                    runtime.reason = (
                        "rapid_rise" if dynamic_candidate and not absolute_candidate
                        else "absolute_flow"
                    )
            return out

        if runtime.phase is DetectorPhase.MONITORING:
            if runtime.reason == "rapid_rise":
                still_candidate = flow >= dynamic_floor
                confirmation = s.burst_rate_confirm_seconds
            else:
                still_candidate = absolute_candidate
                confirmation = s.burst_detection_seconds

            if not still_candidate:
                self._append_transition(
                    out, kind, DetectorPhase.IDLE, now=now, total_l=total_l
                )
            elif self._elapsed(now, runtime.started_at) >= confirmation:
                self._append_transition(
                    out, kind, DetectorPhase.ACTIVE, now=now, total_l=total_l
                )
            return out

        if flow < s.burst_reset_lph:
            runtime.quiet_since = runtime.quiet_since or now
            if self._elapsed(now, runtime.quiet_since) >= s.burst_reset_seconds:
                self._append_transition(
                    out, kind, DetectorPhase.IDLE, now=now, total_l=total_l
                )
        else:
            runtime.quiet_since = None
        return out

    def snapshot(self, total_l: float | None = None) -> EngineSnapshot:
        """Return high-level state derived from detector runtimes."""
        active_kind = self._highest_kind(DetectorPhase.ACTIVE)
        monitoring_kind = self._highest_kind(DetectorPhase.MONITORING)

        if active_kind is not None:
            status = active_kind.value
        elif monitoring_kind is not None:
            status = f"{monitoring_kind.value}_monitoring"
        else:
            status = "idle"

        runtime = self.runtimes[active_kind] if active_kind is not None else None
        return EngineSnapshot(
            status=status,
            alarm_active=active_kind is not None,
            shutoff_request=self._shutoff_request(),
            active_kind=active_kind,
            active_event_id=runtime.event_id if runtime else None,
            active_started_at=runtime.started_at if runtime else None,
            active_detected_at=runtime.detected_at if runtime else None,
            active_volume_l=(
                self._event_volume(runtime, total_l) if runtime is not None else 0.0
            ),
        )

    def _highest_kind(self, phase: DetectorPhase) -> DetectorKind | None:
        found = [kind for kind in DETECTOR_PRIORITY if self.runtimes[kind].phase is phase]
        return found[-1] if found else None

    def _shutoff_request(self) -> bool:
        mapping = {
            DetectorKind.SLOW_LEAK: self.settings.shutoff_slow,
            DetectorKind.LOW_FLOW: self.settings.shutoff_low,
            DetectorKind.HIGH_FLOW: self.settings.shutoff_high,
            DetectorKind.BURST_LEAK: self.settings.shutoff_burst,
        }
        return any(
            runtime.phase is DetectorPhase.ACTIVE and mapping[kind]
            for kind, runtime in self.runtimes.items()
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize runtime state for HA Store."""
        return {
            "last_sample_at": self.last_sample_at.isoformat()
            if self.last_sample_at
            else None,
            "last_flow_lph": self.last_flow_lph,
            "runtimes": {
                kind.value: {
                    "phase": runtime.phase.value,
                    "started_at": runtime.started_at.isoformat()
                    if runtime.started_at
                    else None,
                    "detected_at": runtime.detected_at.isoformat()
                    if runtime.detected_at
                    else None,
                    "quiet_since": runtime.quiet_since.isoformat()
                    if runtime.quiet_since
                    else None,
                    "event_id": runtime.event_id,
                    "start_total_l": runtime.start_total_l,
                    "estimated_volume_l": runtime.estimated_volume_l,
                    "reason": runtime.reason,
                }
                for kind, runtime in self.runtimes.items()
            },
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Restore confirmed events without treating offline time as evidence."""
        # A restart creates an observation gap. Never integrate that gap and never
        # let a pre-restart MONITORING or quiet/reset timer mature while HA was
        # offline. Confirmed ACTIVE events are retained for safety.
        self.last_sample_at = None
        self.last_flow_lph = None
        runtime_data = data.get("runtimes", {})
        if not isinstance(runtime_data, dict):
            return
        for kind in DetectorKind:
            raw = runtime_data.get(kind.value)
            if not isinstance(raw, dict):
                continue

            try:
                phase = DetectorPhase(raw.get("phase", DetectorPhase.IDLE.value))
            except ValueError:
                phase = DetectorPhase.IDLE

            runtime = self.runtimes[kind]
            if phase is not DetectorPhase.ACTIVE:
                runtime.reset()
                continue

            runtime.phase = DetectorPhase.ACTIVE
            runtime.started_at = _parse_datetime(raw.get("started_at"))
            runtime.detected_at = _parse_datetime(raw.get("detected_at"))
            runtime.quiet_since = None
            runtime.event_id = (
                raw.get("event_id") if isinstance(raw.get("event_id"), str) else None
            )
            runtime.start_total_l = _as_float_or_none(raw.get("start_total_l"))
            runtime.estimated_volume_l = (
                _as_float_or_none(raw.get("estimated_volume_l")) or 0.0
            )
            runtime.reason = (
                str(raw.get("reason")) if raw.get("reason") is not None else None
            )


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _as_float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
