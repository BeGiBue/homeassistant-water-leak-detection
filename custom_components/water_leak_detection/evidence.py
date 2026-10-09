"""Deterministic evidence from consecutive fresh, valid flow reports."""

from homeassistant.core import State


class SourceEvidence:
    """Credit completed report intervals without learning a sensor cadence.

    The caller validates each report and breaks the chain on invalid observations.
    A positive expert limit rejects only the current interval, preserving progress.
    """

    def __init__(self) -> None:
        self.signature = None
        self.last_state: State | None = None
        self.received_at: float | None = None
        self.pending_at: float | None = None
        self.credited_seconds = 0.0

    def report(self, received_at: float) -> None:
        self.pending_at = received_at

    def interrupt(self) -> None:
        """Break the measurement chain; recovery starts with zero interval credit."""
        self.received_at = None
        self.pending_at = None
        self.credited_seconds = 0.0

    def expired(self, now: float, configured: float = 0) -> bool:
        """Only an explicit expert limit can identify a silent report gap."""
        return (
            configured > 0 and self.received_at is not None
            and now - self.received_at > configured
        )

    def observe(self, state: State, now: float, configured: float = 0) -> tuple[bool, bool]:
        signature = (id(state), state.last_reported)
        if signature == self.signature and self.pending_at is None:
            return False, False
        self.credited_seconds = 0.0
        received = self.pending_at if self.pending_at is not None else now
        self.pending_at = None
        if self.received_at is not None:
            gap = max(0.0, received - self.received_at)
            if configured <= 0 or gap <= configured:
                self.credited_seconds = gap
        self.received_at = received
        self.signature = signature
        self.last_state = state
        # An excluded interval adds zero; it never resets confirmed progress.
        return True, False
