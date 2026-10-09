"""Fresh report identity and conservative, non-retroactive interval evidence."""

from collections import deque
from math import isclose

from homeassistant.core import State

from .const import TICK_SECONDS


class SourceEvidence:
    """Learn cadence separately from already credited measurement time.

    A new cadence requires repeated comparable intervals. Its discovery only
    permits FUTURE intervals: the interval doing the learning is never credited.
    Alternating cadences retain both modes instead of repeatedly resetting them.
    """

    def __init__(self) -> None:
        self.signature = None
        self.last_state: State | None = None
        self.received_at: float | None = None
        self.intervals: deque[float] = deque(maxlen=20)
        self.candidates: deque[tuple[int, float]] = deque(maxlen=20)
        self.report_index = 0
        self.pending_at: float | None = None
        self.credited_seconds = 0.0
        self.long_outage = False

    def report(self, received_at: float) -> None:
        self.pending_at = received_at

    def limit(self, configured: float = 0) -> float:
        if configured > 0:
            return configured
        return 1.5 * max(self.intervals) if self.intervals else 300.0

    def expired(self, now: float, configured: float = 0) -> bool:
        return self.received_at is not None and now - self.received_at > self.limit(configured)

    def observe(self, state: State, now: float, configured: float = 0) -> tuple[bool, bool]:
        signature = (id(state), state.last_reported)
        if signature == self.signature and self.pending_at is None:
            return False, False
        self.report_index += 1
        received = self.pending_at if self.pending_at is not None else now
        self.pending_at = None
        self.credited_seconds = 0.0
        self.long_outage = False
        interrupted = False
        if self.received_at is not None:
            gap = max(0.0, received - self.received_at)
            # Decide credit from knowledge available BEFORE this report.
            trusted = gap <= configured if configured > 0 else (
                gap <= min(self.intervals, default=TICK_SECONDS)
                or any(isclose(gap, known, rel_tol=0.25) for known in self.intervals)
            )
            interrupted = not trusted
            self.long_outage = gap > max(300.0, self.limit(configured) * 3)
            if self.long_outage:
                self.intervals.clear()
                self.candidates.clear()
            elif not interrupted:
                self.credited_seconds = gap
                if gap > 0:
                    self.intervals.append(gap)
            elif configured <= 0 and gap > 0:
                if any(
                    self.report_index - index <= 4 and isclose(gap, old, rel_tol=0.25)
                    for index, old in self.candidates
                ):
                    self.intervals.append(gap)
                self.candidates.append((self.report_index, gap))
        self.received_at = received
        self.signature = signature
        self.last_state = state
        return True, interrupted
