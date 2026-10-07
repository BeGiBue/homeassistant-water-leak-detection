"""Defensive parsing of persisted runtime data."""

from datetime import UTC, datetime
from math import isfinite
from typing import Any


def parse_datetime(value: Any) -> datetime | None:
    """Accept only timezone-aware timestamps and normalize to UTC."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def nonnegative_float(value: Any) -> float | None:
    """Reject booleans, negative and nonfinite persisted measurements."""
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if isfinite(parsed) and parsed >= 0 else None


def string_set(value: Any) -> set[str]:
    """Parse an optional list of nonempty identifiers."""
    return {item for item in value if isinstance(item, str) and item} if isinstance(
        value, list
    ) else set()
