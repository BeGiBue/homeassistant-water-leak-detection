"""Shared resolution of compatible Low stability option defaults."""

from collections.abc import Mapping
from math import floor
from typing import Any

from .const import (
    CONF_LOW_DETECTION_MIN,
    CONF_LOW_STABILITY_EARLY_MIN,
    CONF_LOW_STABILITY_WINDOW_MIN,
    DEFAULT_LOW_DETECTION_MIN,
    DEFAULT_LOW_STABILITY_EARLY_MIN,
    DEFAULT_LOW_STABILITY_WINDOW_MIN,
)


def low_stability_minutes(options: Mapping[str, Any]) -> tuple[float, float]:
    """Resolve only missing times, preserving explicit values without migration.

    Normal Low detection is at least 1 min in the UI. Round derived times down
    to its stability selectors' 0.1-min grid, with a 0.1-min minimum. Use the
    resolved early time for a missing window, including an explicit early time.
    """
    normal = float(options.get(CONF_LOW_DETECTION_MIN, DEFAULT_LOW_DETECTION_MIN))
    early_default = floor(max(0.1, min(DEFAULT_LOW_STABILITY_EARLY_MIN, normal / 2)) * 10) / 10
    early = float(options.get(CONF_LOW_STABILITY_EARLY_MIN, early_default))
    window_default = floor(max(0.1, min(DEFAULT_LOW_STABILITY_WINDOW_MIN, early / 2)) * 10) / 10
    window = float(options.get(CONF_LOW_STABILITY_WINDOW_MIN, window_default))
    return early, window
