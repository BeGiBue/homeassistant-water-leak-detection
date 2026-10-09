"""Fresh valid report chains and deterministic, completed measurement intervals."""

from homeassistant.core import State


class SourceEvidence:
    """Credit completed intervals only when both endpoints are fresh valid reports.

    No cadence is inferred. A positive expert limit excludes only that interval;
    explicit invalid source observations break the chain until a new valid report.
    """

    def __init__(self) -> None:
        self.signature = None
        self.last_state: State | None = None
        self.received_at: float | None = None
        self.pending_at: float | None = None
        self.credited_seconds = 0.0

    def report(self, received_at: float) -> None:
        self.pending_at = received_at

    def invalidate(self) -> None:
        """An observed invalid source interrupts the measurement chain."""
        self.received_at = None
        self.pending_at = None
        self.credited_seconds = 0.0

    def expired(self, now: float, configured: float = 0) -> bool:
        """Only an explicitly configured expert limit can mark silent expiry."""
        return (
            configured > 0 and self.received_at is not None
            and now - self.received_at > configured
        )

    def observe(self, state: State, now: float, configured: float = 0) -> tuple[bool, bool]:
        signature = (id(state), state.last_reported)
        if signature == self.signature and self.pending_at is None:
            return False, False
        received = self.pending_at if self.pending_at is not None else now
        self.pending_at = None
        self.credited_seconds = 0.0
        excluded = False
        if self.received_at is not None:
            gap = max(0.0, received - self.received_at)
            excluded = configured > 0 and gap > configured
            if not excluded:
                self.credited_seconds = gap
        self.received_at = received
        self.signature = signature
        self.last_state = state
        return True, excluded
