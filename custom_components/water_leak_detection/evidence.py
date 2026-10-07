"""Measurement identity and monotonic report cadence, independent of UTC ordering."""

from collections import deque
from math import isclose

from homeassistant.core import State

from .const import TICK_SECONDS


class SourceEvidence:
    """Only new reports supply evidence; ticks never advance detector intervals.

    The first slow interval establishes cadence without counting unknown startup
    time. Two intervals establish cadence; gaps over 1.5 observed periods restart
    qualification. Outages are not trained immediately as normal. Very slow
    startup periods require repeated matching reports, not a fixed short expiry.
    """

    def __init__(self) -> None:
        self.signature = None
        self.last_state: State | None = None
        self.received_at: float | None = None
        self.intervals: deque[float] = deque(maxlen=5)
        self.pending_at: float | None = None
        self.candidate_gap: float | None = None

    def report(self, received_at: float) -> None:
        self.pending_at = received_at

    def limit(self, configured: float = 0) -> float:
        if configured > 0:
            return configured
        return 1.5 * max(self.intervals) if len(self.intervals) >= 2 else 300.0

    def expired(self, now: float, configured: float = 0) -> bool:
        return self.received_at is not None and now - self.received_at > self.limit(configured)

    def observe(self, state: State, now: float, configured: float = 0) -> tuple[bool, bool]:
        signature = (id(state), state.last_reported)
        if signature == self.signature and self.pending_at is None:
            return False, False
        received = self.pending_at if self.pending_at is not None else now
        self.pending_at = None
        interrupted = False
        if self.received_at is not None:
            gap = max(0.0, received - self.received_at)
            interrupted = gap > self.limit(configured) or (
                not self.intervals and gap > TICK_SECONDS
            )
            if gap > self.limit(configured):
                if (
                    configured <= 0 and not self.intervals and self.candidate_gap is not None
                    and isclose(gap, self.candidate_gap, rel_tol=0.25)
                ):
                    # Repeated slow startup periods can establish cadence, but
                    # their formerly unknown time is still not detector evidence.
                    self.intervals.extend((self.candidate_gap, gap))
                    self.candidate_gap = None
                else:
                    self.intervals.clear()
                    self.candidate_gap = gap if configured <= 0 else None
            elif gap > 0:
                self.intervals.append(gap)
                self.candidate_gap = None
        self.received_at = received
        self.signature = signature
        self.last_state = state  # Retain identity; Python cannot recycle this ID.
        return True, interrupted
